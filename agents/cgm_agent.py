# agents/cgm_agent.py
from agno.agent import Agent
from agno.models.google import Gemini
from typing import Dict, Any, List
import sys
import os
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from utils.database import DatabaseManager

class CGMAgent(Agent):
    def __init__(self, authenticated_user_id: str = None):
        super().__init__(
            name="CGMAgent",
            model=Gemini(
            id=os.environ['DEFAULT_MODEL'],
            vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI'],
            project_id=os.environ['GOOGLE_CLOUD_PROJECT'],
            location=os.environ['GOOGLE_CLOUD_LOCATION'],
            api_key=os.environ.get('GOOGLE_API_KEY')),
            description="Processes glucose readings and provides alerts and insights",
            instructions=[
                "You are a CGM (Continuous Glucose Monitor) specialist.",
                "Validate glucose readings and provide appropriate alerts.",
                "Normal range is 70-180 mg/dL, but adjust based on user's medical conditions.",
                "Provide actionable advice for out-of-range readings.",
                "Track patterns and provide insights on glucose trends.",
                "Be supportive and non-alarming while being medically accurate."
            ],
            show_tool_calls=True,
            markdown=True
        )
        self.db = DatabaseManager()
        self.authenticated_user_id = authenticated_user_id
        
        # CGM ranges based on conditions
        self.cgm_ranges = {
            "Type 1 Diabetes": {"min": 80, "max": 250, "target_min": 80, "target_max": 180},
            "Type 2 Diabetes": {"min": 90, "max": 220, "target_min": 90, "target_max": 180},
            "Pre-diabetes": {"min": 85, "max": 180, "target_min": 85, "target_max": 140},
            "None": {"min": 70, "max": 140, "target_min": 70, "target_max": 140},
            "default": {"min": 70, "max": 180, "target_min": 80, "target_max": 140}
        }
        
        # Add custom tools
        self.add_tool(self.process_glucose_reading)
        self.add_tool(self.get_glucose_trends)
        self.add_tool(self.get_recent_alerts)
        self.add_tool(self.validate_reading_range)
    
    def set_authenticated_user(self, user_id: str):
        """Set the authenticated user for this session"""
        self.authenticated_user_id = user_id
    
    def get_user_cgm_range(self, user_id: str) -> Dict[str, int]:
        """Get appropriate CGM range for user based on medical conditions"""
        user_data = self.db.validate_user_id(user_id)
        if not user_data:
            return self.cgm_ranges["default"]
        
        conditions = user_data['medical_conditions']
        
        # Priority order for conditions
        if "Type 1 Diabetes" in conditions:
            return self.cgm_ranges["Type 1 Diabetes"]
        elif "Type 2 Diabetes" in conditions:
            return self.cgm_ranges["Type 2 Diabetes"]
        elif "Pre-diabetes" in conditions:
            return self.cgm_ranges["Pre-diabetes"]
        elif "None" in conditions or not conditions:
            return self.cgm_ranges["None"]
        else:
            return self.cgm_ranges["default"]
    
    def process_glucose_reading(self, glucose_reading: float) -> Dict[str, Any]:
        """
        Process a glucose reading and provide alerts if necessary
        
        Args:
            glucose_reading: The glucose reading in mg/dL
            
        Returns:
            Dict containing validation results, alerts, and recommendations
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first before recording glucose readings."
            }
        
        # Validate reading range
        if glucose_reading < 20 or glucose_reading > 600:
            return {
                "status": "error",
                "message": f"Invalid glucose reading: {glucose_reading} mg/dL. Please check your meter and try again."
            }
        
        user_ranges = self.get_user_cgm_range(self.authenticated_user_id)
        
        # Determine alert level
        alert_type = "normal"
        message = f"Glucose reading recorded: {glucose_reading} mg/dL"
        recommendations = []
        
        if glucose_reading < user_ranges["target_min"]:
            if glucose_reading < 70:
                alert_type = "critical_low"
                message = f"🚨 CRITICAL LOW: {glucose_reading} mg/dL"
                recommendations = [
                    "Consume 15g of fast-acting carbs immediately",
                    "Test again in 15 minutes",
                    "Contact healthcare provider if severe symptoms"
                ]
            else:
                alert_type = "low"
                message = f"⚠️ LOW: {glucose_reading} mg/dL"
                recommendations = [
                    "Consider a small snack with carbohydrates",
                    "Monitor closely for symptoms",
                    "Test again in 30 minutes"
                ]
        elif glucose_reading > user_ranges["target_max"]:
            if glucose_reading > 250:
                alert_type = "critical_high"
                message = f"🚨 CRITICAL HIGH: {glucose_reading} mg/dL"
                recommendations = [
                    "Check for ketones if diabetic",
                    "Stay hydrated",
                    "Contact healthcare provider immediately",
                    "Avoid strenuous exercise"
                ]
            else:
                alert_type = "high"
                message = f"⚠️ HIGH: {glucose_reading} mg/dL"
                recommendations = [
                    "Stay hydrated",
                    "Consider light physical activity if safe",
                    "Monitor carbohydrate intake",
                    "Test again in 1-2 hours"
                ]
        else:
            message = f"✅ NORMAL: {glucose_reading} mg/dL - Great job!"
            recommendations = ["Keep up the good work!", "Continue current management plan"]
        
        # Always store the CGM reading
        self.db.store_cgm_reading(self.authenticated_user_id, glucose_reading)
        
        # Log the interaction for tracking
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "CGMAgent",
            "Database",
            "glucose_logging",
            f"Reading: {glucose_reading} mg/dL, Alert: {alert_type}"
        )
        
        # Store alert if not normal
        if alert_type != "normal":
            self.db.store_cgm_alert(
                self.authenticated_user_id, 
                glucose_reading, 
                alert_type, 
                message
            )
        
        # Add glucose-based recommendations
        glucose_recommendations = self._get_glucose_based_recommendations(glucose_reading, user_ranges)
        if glucose_recommendations:
            recommendations.extend(glucose_recommendations)
        
        return {
            "status": "success",
            "reading": glucose_reading,
            "alert_type": alert_type,
            "message": message,
            "recommendations": recommendations,
            "target_range": f"{user_ranges['target_min']}-{user_ranges['target_max']} mg/dL"
        }
    
    def _get_glucose_based_recommendations(self, reading: float, user_ranges: Dict[str, int]) -> List[str]:
        """Get personalized recommendations based on glucose reading"""
        recommendations = []
        
        if reading < user_ranges["target_min"]:
            recommendations.append("Consider having a small snack with protein and complex carbs")
            recommendations.append("Monitor for symptoms of hypoglycemia")
        elif reading > user_ranges["target_max"]:
            recommendations.append("Consider light physical activity if safe")
            recommendations.append("Stay well hydrated")
            recommendations.append("Monitor for symptoms of hyperglycemia")
        
        # Add trend-based recommendations
        recent_trends = self.db.get_cgm_trends(self.authenticated_user_id, 3)
        if recent_trends["readings_count"] >= 2:
            if recent_trends["trend"] == "increasing":
                recommendations.append("Your glucose has been trending higher - consider reviewing recent meals")
            elif recent_trends["trend"] == "decreasing":
                recommendations.append("Your glucose has been trending lower - monitor for hypoglycemia")
        
        return recommendations
    
    def validate_reading_range(self, glucose_reading: float) -> Dict[str, Any]:
        """
        Validate if a glucose reading is within acceptable measurement range
        
        Args:
            glucose_reading: The glucose reading to validate
            
        Returns:
            Dict containing validation results
        """
        if glucose_reading < 20:
            return {
                "valid": False,
                "message": "Reading too low - glucose meters typically can't measure below 20 mg/dL"
            }
        elif glucose_reading > 600:
            return {
                "valid": False,
                "message": "Reading too high - please check your meter and try again"
            }
        elif glucose_reading < 80 or glucose_reading > 300:
            return {
                "valid": True,
                "message": "Reading is in measurable range but may require immediate attention",
                "warning": True
            }
        else:
            return {
                "valid": True,
                "message": "Reading is within normal measurement range"
            }
    
    def get_glucose_trends(self, days: int = 7) -> Dict[str, Any]:
        """
        Get glucose trends and patterns for the user
        
        Args:
            days: Number of days to analyze (default 7)
            
        Returns:
            Dict containing trend analysis and insights
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to view glucose trends."
            }
        
        # Use the enhanced database method
        cgm_data = self.db.get_cgm_trends(self.authenticated_user_id, days)
        
        if cgm_data["readings_count"] == 0:
            return {
                "status": "success",
                "message": f"No glucose readings found in the past {days} days.",
                "readings_count": 0
            }
        
        # Log the interaction for tracking
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "CGMAgent",
            "User",
            "trend_analysis",
            f"Analyzed {cgm_data['readings_count']} glucose readings over {days} days"
        )
        
        user_ranges = self.get_user_cgm_range(self.authenticated_user_id)
        
        # Calculate time in range
        readings = self.db.get_recent_cgm_readings(self.authenticated_user_id, days)
        in_range_count = sum(1 for r in readings if user_ranges['target_min'] <= r['reading'] <= user_ranges['target_max'])
        time_in_range = (in_range_count / len(readings)) * 100 if readings else 0
        
        return {
            "status": "success",
            "readings_count": cgm_data["readings_count"],
            "average_glucose": cgm_data["average_glucose"],
            "trend": cgm_data["trend"],
            "time_in_range": round(time_in_range, 1),
            "target_range": f"{user_ranges['target_min']}-{user_ranges['target_max']} mg/dL",
            "recent_readings": cgm_data["recent_readings"]
        }
    
    def get_recent_alerts(self, days: int = 7) -> Dict[str, Any]:
        """
        Get recent CGM alerts for the user
        
        Args:
            days: Number of days to look back (default 7)
            
        Returns:
            Dict containing recent alerts
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to view alerts."
            }
        
        from datetime import datetime, timedelta
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            since_date = datetime.now() - timedelta(days=days)
            cursor.execute(
                """SELECT reading, alert_type, message, timestamp 
                   FROM cgm_alerts 
                   WHERE user_id = ? AND timestamp >= ? 
                   ORDER BY timestamp DESC LIMIT 10""",
                (self.authenticated_user_id, since_date.isoformat())
            )
            results = cursor.fetchall()
        
        alerts = [
            {
                "reading": row[0],
                "alert_type": row[1],
                "message": row[2],
                "timestamp": row[3]
            }
            for row in results
        ]
        
        return {
            "status": "success",
            "alerts_count": len(alerts),
            "alerts": alerts
        }

# Convenience function to create the agent
def create_cgm_agent(authenticated_user_id: str = None):
    return CGMAgent(authenticated_user_id)