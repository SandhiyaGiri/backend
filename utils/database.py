# utils/database.py
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("DATABASE_PATH", "database/synthetic_health_data.db")
        self.init_agent_tables()
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_agent_tables(self):
        """Initialize tables for agent-specific data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Mood tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mood_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    mood_label TEXT NOT NULL,
                    mood_score INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # CGM readings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cgm_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    reading REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # CGM alerts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cgm_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    reading REAL NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Food intake table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS food_intake (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    meal_description TEXT NOT NULL,
                    carbs REAL,
                    protein REAL,
                    fat REAL,
                    calories REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Meal plans table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS meal_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    plan_date DATE NOT NULL,
                    breakfast TEXT NOT NULL,
                    lunch TEXT NOT NULL,
                    dinner TEXT NOT NULL,
                    total_calories REAL,
                    total_carbs REAL,
                    total_protein REAL,
                    total_fat REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Agent interaction log table for tracking cross-agent communication
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    source_agent TEXT NOT NULL,
                    target_agent TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    data_summary TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            conn.commit()
    
    def validate_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Validate user ID and return user data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, name, city, dietary_category, medical_conditions FROM users WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            
            if result:
                return {
                    'user_id': result[0],
                    'name': result[1],
                    'city': result[2],
                    'dietary_category': result[3],
                    'medical_conditions': json.loads(result[4])
                }
            return None
    
    def get_user_by_name(self, name: str) -> List[Dict[str, Any]]:
        """Search users by name (partial match)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, name, city FROM users WHERE name LIKE ?",
                (f"%{name}%",)
            )
            results = cursor.fetchall()
            
            return [
                {'user_id': row[0], 'name': row[1], 'city': row[2]}
                for row in results
            ]
    
    def store_mood(self, user_id: str, mood_label: str, mood_score: int):
        """Store mood data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mood_tracking (user_id, mood_label, mood_score) VALUES (?, ?, ?)",
                (user_id, mood_label, mood_score)
            )
            conn.commit()
    
    def get_mood_rolling_average(self, user_id: str, days: int = 7) -> float:
        """Get rolling average of mood scores"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            since_date = datetime.now() - timedelta(days=days)
            cursor.execute(
                "SELECT AVG(mood_score) FROM mood_tracking WHERE user_id = ? AND timestamp >= ?",
                (user_id, since_date.isoformat())
            )
            result = cursor.fetchone()
            return round(result[0], 2) if result[0] else 0.0
    
    def get_recent_mood_data(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive recent mood data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            since_date = datetime.now() - timedelta(days=days)
            cursor.execute(
                """SELECT mood_label, mood_score, timestamp 
                   FROM mood_tracking 
                   WHERE user_id = ? AND timestamp >= ? 
                   ORDER BY timestamp DESC""",
                (user_id, since_date.isoformat())
            )
            results = cursor.fetchall()
            
            if not results:
                return {"entries_count": 0, "average_mood": 0, "trend": "no_data"}
            
            scores = [row[1] for row in results]
            avg_mood = sum(scores) / len(scores)
            
            # Determine trend
            if len(scores) >= 2:
                recent_avg = sum(scores[:len(scores)//2]) / (len(scores)//2)
                older_avg = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
                
                if recent_avg > older_avg + 0.5:
                    trend = "improving"
                elif recent_avg < older_avg - 0.5:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"
            
            return {
                "entries_count": len(results),
                "average_mood": round(avg_mood, 1),
                "trend": trend,
                "recent_entries": [
                    {"mood": row[0], "score": row[1], "timestamp": row[2]}
                    for row in results[:5]
                ]
            }
    
    def store_cgm_reading(self, user_id: str, reading: float):
        """Store CGM reading"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO cgm_readings (user_id, reading) VALUES (?, ?)",
                (user_id, reading)
            )
            conn.commit()
    
    def store_cgm_alert(self, user_id: str, reading: float, alert_type: str, message: str):
        """Store CGM alert"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO cgm_alerts (user_id, reading, alert_type, message) VALUES (?, ?, ?, ?)",
                (user_id, reading, alert_type, message)
            )
            conn.commit()
    
    def get_recent_cgm_readings(self, user_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent CGM readings"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            since_date = datetime.now() - timedelta(days=days)
            cursor.execute(
                """SELECT reading, timestamp FROM cgm_readings 
                   WHERE user_id = ? AND timestamp >= ? 
                   ORDER BY timestamp DESC""",
                (user_id, since_date.isoformat())
            )
            results = cursor.fetchall()
            
            return [
                {'reading': row[0], 'timestamp': row[1]}
                for row in results
            ]
    
    def get_cgm_trends(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive CGM trend data"""
        readings = self.get_recent_cgm_readings(user_id, days)
        
        if not readings:
            return {"readings_count": 0, "average_glucose": 0, "trend": "no_data"}
        
        values = [r['reading'] for r in readings]
        avg_glucose = sum(values) / len(values)
        
        # Determine trend
        if len(values) >= 3:
            recent_avg = sum(values[:len(values)//2]) / (len(values)//2)
            older_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
            
            if recent_avg > older_avg + 20:
                trend = "increasing"
            elif recent_avg < older_avg - 20:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "readings_count": len(readings),
            "average_glucose": round(avg_glucose, 1),
            "trend": trend,
            "recent_readings": readings[:5]
        }
    
    def store_food_intake(self, user_id: str, meal_description: str, nutrients: Dict[str, float]):
        """Store food intake data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO food_intake (user_id, meal_description, carbs, protein, fat, calories) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, meal_description, nutrients.get('carbs'), 
                 nutrients.get('protein'), nutrients.get('fat'), nutrients.get('calories'))
            )
            conn.commit()
    
    def get_recent_nutrition_data(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive recent nutrition data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            since_date = datetime.now() - timedelta(days=days)
            cursor.execute(
                """SELECT meal_description, carbs, protein, fat, calories, timestamp 
                   FROM food_intake 
                   WHERE user_id = ? AND timestamp >= ? 
                   ORDER BY timestamp DESC""",
                (user_id, since_date.isoformat())
            )
            results = cursor.fetchall()
            
            if not results:
                return {"entries_count": 0, "average_calories": 0, "trend": "no_data"}
            
            # Calculate averages
            total_calories = sum(row[4] or 0 for row in results)
            total_carbs = sum(row[1] or 0 for row in results)
            total_protein = sum(row[2] or 0 for row in results)
            total_fat = sum(row[3] or 0 for row in results)
            
            avg_calories = total_calories / len(results)
            avg_carbs = total_carbs / len(results)
            avg_protein = total_protein / len(results)
            avg_fat = total_fat / len(results)
            
            return {
                "entries_count": len(results),
                "average_calories": round(avg_calories, 1),
                "average_carbs": round(avg_carbs, 1),
                "average_protein": round(avg_protein, 1),
                "average_fat": round(avg_fat, 1),
                "recent_entries": [
                    {
                        "meal": row[0], "carbs": row[1], "protein": row[2], 
                        "fat": row[3], "calories": row[4], "timestamp": row[5]
                    }
                    for row in results[:5]
                ]
            }
    
    def store_meal_plan(self, user_id: str, plan_date: str, meal_plan: Dict[str, Any]):
        """Store generated meal plan"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO meal_plans (user_id, plan_date, breakfast, lunch, dinner, 
                   total_calories, total_carbs, total_protein, total_fat) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, plan_date, meal_plan['breakfast'], meal_plan['lunch'], 
                 meal_plan['dinner'], meal_plan.get('total_calories'),
                 meal_plan.get('total_carbs'), meal_plan.get('total_protein'), 
                 meal_plan.get('total_fat'))
            )
            conn.commit()
    
    def log_agent_interaction(self, user_id: str, source_agent: str, target_agent: str, 
                            data_type: str, data_summary: str = None):
        """Log cross-agent interactions for tracking"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO agent_interactions (user_id, source_agent, target_agent, data_type, data_summary) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, source_agent, target_agent, data_type, data_summary)
            )
            conn.commit()
    
    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive user context for meal planning and other agents"""
        user_data = self.validate_user_id(user_id)
        if not user_data:
            return None
        
        # Get recent mood data
        mood_data = self.get_recent_mood_data(user_id, 7)
        
        # Get recent CGM data
        cgm_data = self.get_cgm_trends(user_id, 7)
        
        # Get recent nutrition data
        nutrition_data = self.get_recent_nutrition_data(user_id, 7)
        
        # Build comprehensive context
        context = {
            **user_data,
            'recent_mood_avg': mood_data.get('average_mood', 0),
            'mood_trend': mood_data.get('trend', 'no_data'),
            'mood_entries_count': mood_data.get('entries_count', 0),
            'recent_cgm_avg': cgm_data.get('average_glucose', 0),
            'cgm_trend': cgm_data.get('trend', 'no_data'),
            'cgm_readings_count': cgm_data.get('readings_count', 0),
            'recent_calories_avg': nutrition_data.get('average_calories', 0),
            'recent_carbs_avg': nutrition_data.get('average_carbs', 0),
            'recent_protein_avg': nutrition_data.get('average_protein', 0),
            'recent_fat_avg': nutrition_data.get('average_fat', 0),
            'nutrition_entries_count': nutrition_data.get('entries_count', 0)
        }
        
        return context
    
    def get_health_summary(self, user_id: str) -> Dict[str, Any]:
        """Get a comprehensive health summary for dashboard display"""
        context = self.get_user_context(user_id)
        if not context:
            return None
        
        summary = {
            "user_info": {
                "name": context["name"],
                "dietary_category": context["dietary_category"],
                "medical_conditions": context["medical_conditions"]
            },
            "mood_summary": {
                "average": context["recent_mood_avg"],
                "trend": context["mood_trend"],
                "entries_count": context["mood_entries_count"]
            },
            "glucose_summary": {
                "average": context["recent_cgm_avg"],
                "trend": context["cgm_trend"],
                "readings_count": context["cgm_readings_count"]
            },
            "nutrition_summary": {
                "average_calories": context["recent_calories_avg"],
                "average_carbs": context["recent_carbs_avg"],
                "average_protein": context["recent_protein_avg"],
                "average_fat": context["recent_fat_avg"],
                "entries_count": context["nutrition_entries_count"]
            }
        }
        
        return summary