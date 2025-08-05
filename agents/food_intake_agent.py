# agents/food_intake_agent.py
from agno.agent import Agent
from agno.models.google import Gemini
from typing import Dict, Any, List, Optional
import sys
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
import os

load_dotenv()

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from utils.database import DatabaseManager
from utils.client import GeminiClient

class FoodIntakeAgent(Agent):
    def __init__(self, authenticated_user_id: str = None):
        super().__init__(
            name="FoodIntakeAgent",
            model=Gemini(
            id=os.environ['DEFAULT_MODEL'],
            vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI'],
            project_id=os.environ['GOOGLE_CLOUD_PROJECT'],
            location=os.environ['GOOGLE_CLOUD_LOCATION'],
            api_key=os.environ.get('GOOGLE_API_KEY')),
            description="Analyzes meal descriptions and categorizes nutrients using LLM",
            instructions=[
                "You are a nutrition specialist that analyzes food intake.",
                "Parse meal descriptions and estimate macronutrients accurately.",
                "Provide helpful feedback on nutritional balance.",
                "Consider portion sizes and cooking methods in your analysis.",
                "Be encouraging while providing accurate nutritional information.",
                "Help users understand the nutritional value of their meals."
            ],
            show_tool_calls=True,
            markdown=True
        )
        self.db = DatabaseManager()
        self.llm_client = GeminiClient()
        self.authenticated_user_id = authenticated_user_id
        
        # Add custom tools
        self.add_tool(self.log_meal)
        self.add_tool(self.analyze_meal_description)
        self.add_tool(self.get_daily_nutrition_summary)
        self.add_tool(self.get_nutrition_insights)
        self.add_tool(self.suggest_nutritional_improvements)
    
    def set_authenticated_user(self, user_id: str):
        """Set the authenticated user for this session"""
        self.authenticated_user_id = user_id
    
    def analyze_meal_description(self, meal_description: str, timestamp: str = None) -> Dict[str, Any]:
        """
        Analyze a meal description and estimate nutritional content
        
        Args:
            meal_description: Free-text description of the meal
            timestamp: Optional timestamp (if not provided, uses current time)
            
        Returns:
            Dict containing nutritional analysis
        """
        if not meal_description.strip():
            return {
                "status": "error",
                "message": "Please provide a meal description to analyze."
            }
        
        # Use LLM to categorize nutrients
        try:
            nutrients = self.llm_client.categorize_food_nutrients(meal_description)
            
            # Validate and clean nutrients
            for key in ['carbs', 'protein', 'fat', 'calories']:
                if key not in nutrients or not isinstance(nutrients[key], (int, float)):
                    nutrients[key] = 0.0
                else:
                    nutrients[key] = round(float(nutrients[key]), 1)
            
            # Generate nutritional feedback
            feedback = self._generate_nutrition_feedback(nutrients, meal_description)
            
            return {
                "status": "success",
                "meal_description": meal_description,
                "nutrients": nutrients,
                "feedback": feedback,
                "timestamp": timestamp or datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error analyzing meal: {str(e)}",
                "fallback_nutrients": {
                    "carbs": 30.0,
                    "protein": 15.0,
                    "fat": 10.0,
                    "calories": 250.0
                }
            }
    
    def log_meal(self, meal_description: str, timestamp: str = None) -> Dict[str, Any]:
        """
        Log a meal with nutritional analysis
        
        Args:
            meal_description: Free-text description of the meal
            timestamp: Optional timestamp for the meal
            
        Returns:
            Dict containing confirmation and nutritional summary
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first before logging meals."
            }
        
        # Analyze the meal
        analysis = self.analyze_meal_description(meal_description, timestamp)
        
        if analysis["status"] == "error":
            return analysis
        
        # Store in database
        nutrients = analysis["nutrients"]
        self.db.store_food_intake(self.authenticated_user_id, meal_description, nutrients)
        
        # Log the interaction for tracking
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "FoodIntakeAgent",
            "Database",
            "meal_logging",
            f"Meal: {meal_description[:50]}... (Calories: {nutrients['calories']})"
        )
        
        # Get user's dietary preferences for additional feedback
        user_data = self.db.validate_user_id(self.authenticated_user_id)
        dietary_feedback = ""
        
        if user_data:
            dietary_category = user_data['dietary_category']
            medical_conditions = user_data['medical_conditions']
            dietary_feedback = self._get_dietary_specific_feedback(
                nutrients, dietary_category, medical_conditions
            )
        
        # Get recent nutrition context for better feedback
        recent_nutrition = self.db.get_recent_nutrition_data(self.authenticated_user_id, 1)
        context_feedback = self._get_context_based_feedback(nutrients, recent_nutrition)
        
        message = f"✅ Meal logged successfully!\n\n"
        message += f"**Nutritional Breakdown:**\n"
        message += f"• Carbohydrates: {nutrients['carbs']}g\n"
        message += f"• Protein: {nutrients['protein']}g\n"
        message += f"• Fat: {nutrients['fat']}g\n"
        message += f"• Calories: {nutrients['calories']} kcal\n\n"
        message += f"**Feedback:** {analysis['feedback']}"
        
        if dietary_feedback:
            message += f"\n\n**Dietary Notes:** {dietary_feedback}"
        
        if context_feedback:
            message += f"\n\n**Context:** {context_feedback}"
        
        return {
            "status": "success",
            "message": message,
            "nutrients": nutrients,
            "meal_description": meal_description,
            "context_feedback": context_feedback
        }
    
    def get_daily_nutrition_summary(self, date: str = None) -> Dict[str, Any]:
        """
        Get nutritional summary for a specific day
        
        Args:
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Dict containing daily nutrition totals and analysis
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to view nutrition summary."
            }
        
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT meal_description, carbs, protein, fat, calories, timestamp
                   FROM food_intake 
                   WHERE user_id = ? AND DATE(timestamp) = ?
                   ORDER BY timestamp""",
                (self.authenticated_user_id, date)
            )
            results = cursor.fetchall()
        
        if not results:
            return {
                "status": "success",
                "message": f"No meals logged for {date}.",
                "date": date,
                "meals_count": 0
            }
        
        # Calculate totals
        total_carbs = sum(row[1] or 0 for row in results)
        total_protein = sum(row[2] or 0 for row in results)
        total_fat = sum(row[3] or 0 for row in results)
        total_calories = sum(row[4] or 0 for row in results)
        
        # Calculate macronutrient percentages
        total_macro_calories = (total_carbs * 4) + (total_protein * 4) + (total_fat * 9)
        if total_macro_calories > 0:
            carb_percent = round((total_carbs * 4 / total_macro_calories) * 100, 1)
            protein_percent = round((total_protein * 4 / total_macro_calories) * 100, 1)
            fat_percent = round((total_fat * 9 / total_macro_calories) * 100, 1)
        else:
            carb_percent = protein_percent = fat_percent = 0
        
        # Generate meals list
        meals = [
            {
                "description": row[0],
                "carbs": row[1],
                "protein": row[2],
                "fat": row[3],
                "calories": row[4],
                "timestamp": row[5]
            }
            for row in results
        ]
        
        # Nutritional assessment
        assessment = self._assess_daily_nutrition(
            total_carbs, total_protein, total_fat, total_calories,
            carb_percent, protein_percent, fat_percent
        )
        
        return {
            "status": "success",
            "date": date,
            "meals_count": len(results),
            "totals": {
                "carbs": round(total_carbs, 1),
                "protein": round(total_protein, 1),
                "fat": round(total_fat, 1),
                "calories": round(total_calories, 1)
            },
            "percentages": {
                "carbs": carb_percent,
                "protein": protein_percent,
                "fat": fat_percent
            },
            "meals": meals,
            "assessment": assessment
        }
    
    def get_nutrition_insights(self, days: int = 7) -> Dict[str, Any]:
        """
        Get nutrition insights and patterns over multiple days
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dict containing nutrition insights and trends
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to view nutrition insights."
            }
        
        # Use the enhanced database method
        nutrition_data = self.db.get_recent_nutrition_data(self.authenticated_user_id, days)
        
        if nutrition_data["entries_count"] == 0:
            return {
                "status": "success",
                "message": f"No meal data found in the past {days} days.",
                "days_analyzed": 0
            }
        
        # Log the interaction for tracking
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "FoodIntakeAgent",
            "User",
            "nutrition_analysis",
            f"Analyzed {nutrition_data['entries_count']} meals over {days} days"
        )
        
        # Calculate averages
        avg_carbs = nutrition_data["average_carbs"]
        avg_protein = nutrition_data["average_protein"]
        avg_fat = nutrition_data["average_fat"]
        avg_calories = nutrition_data["average_calories"]
        
        # Identify patterns
        patterns = []
        
        # Calorie consistency
        if avg_calories < 1200:
            patterns.append("Your calorie intake is below typical daily needs")
        elif avg_calories > 2500:
            patterns.append("Your calorie intake is above typical daily needs")
        else:
            patterns.append("Your calorie intake is within typical daily ranges")
        
        # Protein adequacy
        if avg_protein < 50:
            patterns.append("Your protein intake may be below recommended levels")
        elif avg_protein > 120:
            patterns.append("You're getting plenty of protein in your diet")
        else:
            patterns.append("Your protein intake is well-balanced")
        
        # Meal frequency
        if nutrition_data["entries_count"] < days * 2:
            patterns.append("You might benefit from eating more frequent meals")
        else:
            patterns.append("You maintain a good meal frequency")
        
        # Generate recommendations
        recommendations = self._generate_nutrition_recommendations(
            avg_carbs, avg_protein, avg_fat, avg_calories, patterns
        )
        
        return {
            "status": "success",
            "days_analyzed": days,
            "averages": {
                "carbs": avg_carbs,
                "protein": avg_protein,
                "fat": avg_fat,
                "calories": avg_calories,
                "meals_per_day": round(nutrition_data["entries_count"] / days, 1)
            },
            "patterns": patterns,
            "recommendations": recommendations,
            "recent_entries": nutrition_data["recent_entries"]
        }
    
    def suggest_nutritional_improvements(self) -> Dict[str, Any]:
        """
        Suggest nutritional improvements based on recent intake
        
        Returns:
            Dict containing personalized nutrition suggestions
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to get nutrition suggestions."
            }
        
        # Get recent nutrition data
        insights = self.get_nutrition_insights(7)
        if insights["days_analyzed"] == 0:
            return {
                "status": "success",
                "message": "Log some meals first to get personalized nutrition suggestions!"
            }
        
        averages = insights["averages"]
        suggestions = []
        
        # Protein suggestions
        if averages["protein"] < 50:
            suggestions.append({
                "category": "Protein",
                "issue": "Low protein intake",
                "suggestion": "Add lean meats, fish, eggs, legumes, or Greek yogurt to your meals",
                "target": "Aim for 0.8-1.2g per kg of body weight daily"
            })
        
        # Fiber/Carb quality suggestions
        if averages["carbs"] > averages["protein"] * 3:
            suggestions.append({
                "category": "Carbohydrates",
                "issue": "High carbohydrate ratio",
                "suggestion": "Focus on complex carbs like whole grains, vegetables, and fruits",
                "target": "Balance carbs with protein and healthy fats"
            })
        
        # Healthy fats
        if averages["fat"] < 30:
            suggestions.append({
                "category": "Healthy Fats",
                "issue": "Low fat intake",
                "suggestion": "Include nuts, seeds, avocado, olive oil, and fatty fish",
                "target": "20-35% of total calories from healthy fats"
            })
        
        # Calorie adequacy
        if averages["calories"] < 1200:
            suggestions.append({
                "category": "Energy",
                "issue": "Very low calorie intake",
                "suggestion": "Consider adding nutrient-dense snacks between meals",
                "target": "Ensure adequate energy for your activity level"
            })
        elif averages["calories"] > 2500:
            suggestions.append({
                "category": "Energy",
                "issue": "High calorie intake",
                "suggestion": "Focus on portion control and nutrient-dense foods",
                "target": "Balance calories with your activity level"
            })
        
        # Meal frequency
        if averages["meals_per_day"] < 2:
            suggestions.append({
                "category": "Meal Timing",
                "issue": "Infrequent eating",
                "suggestion": "Try to eat 3 regular meals with healthy snacks if needed",
                "target": "Consistent meal timing supports metabolism"
            })
        
        # Get user-specific suggestions
        user_data = self.db.validate_user_id(self.authenticated_user_id)
        if user_data:
            user_suggestions = self._get_condition_specific_suggestions(
                user_data['medical_conditions'], user_data['dietary_category']
            )
            suggestions.extend(user_suggestions)
        
        return {
            "status": "success",
            "suggestions": suggestions[:6],  # Limit to top 6 suggestions
            "message": "Here are personalized nutrition suggestions based on your recent intake:"
        }
    
    def _generate_nutrition_feedback(self, nutrients: Dict[str, float], meal_description: str) -> str:
        """Generate feedback for a specific meal"""
        feedback_parts = []
        
        # Protein feedback
        if nutrients['protein'] > 25:
            feedback_parts.append("Excellent protein content!")
        elif nutrients['protein'] > 15:
            feedback_parts.append("Good protein source.")
        elif nutrients['protein'] < 5:
            feedback_parts.append("Consider adding more protein.")
        
        # Calorie density
        if nutrients['calories'] > 600:
            feedback_parts.append("High-calorie meal - great for post-workout or busy days.")
        elif nutrients['calories'] < 200:
            feedback_parts.append("Light meal - consider if this meets your energy needs.")
        
        # Macro balance
        if nutrients['carbs'] > nutrients['protein'] * 4:
            feedback_parts.append("Carb-heavy meal - pair with protein if possible.")
        
        return " ".join(feedback_parts) if feedback_parts else "Nutritious meal logged!"
    
    def _get_dietary_specific_feedback(self, nutrients: Dict[str, float], 
                                     dietary_category: str, medical_conditions: List[str]) -> str:
        """Generate feedback specific to dietary preferences and conditions"""
        feedback = []
        
        # Diabetic considerations
        if any(condition in medical_conditions for condition in ["Type 1 Diabetes", "Type 2 Diabetes", "Pre-diabetes"]):
            if nutrients['carbs'] > 45:
                feedback.append("High carb content - monitor blood glucose closely.")
            elif nutrients['carbs'] < 15:
                feedback.append("Low carb meal - good for glucose management.")
        
        # Hypertension considerations
        if "Hypertension" in medical_conditions:
            feedback.append("Consider the sodium content if this meal includes processed foods.")
        
        # Dietary category feedback
        if dietary_category == "Vegan" and nutrients['protein'] < 10:
            feedback.append("As a vegan, ensure adequate plant-based protein sources.")
        elif dietary_category == "Vegetarian" and nutrients['protein'] < 15:
            feedback.append("Consider adding more vegetarian protein sources.")
        
        return " ".join(feedback)
    
    def _assess_daily_nutrition(self, carbs: float, protein: float, fat: float, 
                              calories: float, carb_pct: float, protein_pct: float, fat_pct: float) -> str:
        """Assess overall daily nutrition"""
        assessments = []
        
        # Calorie assessment
        if calories < 1200:
            assessments.append("⚠️ Very low calorie intake today")
        elif calories > 2500:
            assessments.append("⚠️ High calorie intake today")
        else:
            assessments.append("✅ Reasonable calorie intake")
        
        # Macro balance assessment
        if 45 <= carb_pct <= 65 and 15 <= protein_pct <= 25 and 20 <= fat_pct <= 35:
            assessments.append("✅ Well-balanced macronutrients")
        else:
            if protein_pct < 15:
                assessments.append("⚠️ Low protein percentage")
            if carb_pct > 70:
                assessments.append("⚠️ Very high carbohydrate percentage")
            if fat_pct < 15:
                assessments.append("⚠️ Low fat intake")
        
        return " | ".join(assessments)
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def _generate_nutrition_recommendations(self, avg_carbs: float, avg_protein: float, 
                                          avg_fat: float, avg_calories: float, patterns: List[str]) -> List[str]:
        """Generate nutrition recommendations"""
        recommendations = []
        
        if avg_protein < 50:
            recommendations.append("Increase protein intake with lean meats, fish, or plant-based sources")
        
        if avg_calories < 1400:
            recommendations.append("Consider adding healthy snacks to meet energy needs")
        
        if "varies significantly" in " ".join(patterns):
            recommendations.append("Try to maintain more consistent daily calorie intake")
        
        if avg_fat < 30:
            recommendations.append("Include more healthy fats like nuts, seeds, and olive oil")
        
        return recommendations[:4]  # Limit recommendations
    
    def _get_context_based_feedback(self, current_nutrients: Dict[str, float], 
                                  recent_nutrition: Dict[str, Any]) -> str:
        """Get feedback based on recent nutrition context"""
        if recent_nutrition["entries_count"] == 0:
            return ""
        
        feedback_parts = []
        
        # Compare with recent averages
        recent_calories = recent_nutrition.get("average_calories", 0)
        recent_protein = recent_nutrition.get("average_protein", 0)
        
        if recent_calories > 0:
            if current_nutrients["calories"] > recent_calories * 1.5:
                feedback_parts.append("This is higher in calories than your recent meals.")
            elif current_nutrients["calories"] < recent_calories * 0.5:
                feedback_parts.append("This is lower in calories than your recent meals.")
        
        if recent_protein > 0:
            if current_nutrients["protein"] > recent_protein * 1.3:
                feedback_parts.append("Great protein boost compared to your recent intake!")
            elif current_nutrients["protein"] < recent_protein * 0.7:
                feedback_parts.append("Consider adding protein to your next meal.")
        
        # Check for meal timing patterns
        if recent_nutrition["entries_count"] >= 3:
            feedback_parts.append("You're maintaining good meal consistency.")
        
        return " ".join(feedback_parts)
    
    def _get_condition_specific_suggestions(self, medical_conditions: List[str], 
                                          dietary_category: str) -> List[Dict[str, str]]:
        """Get suggestions specific to medical conditions and dietary preferences"""
        suggestions = []
        
        if "Type 1 Diabetes" in medical_conditions or "Type 2 Diabetes" in medical_conditions:
            suggestions.append({
                "category": "Diabetes Management",
                "issue": "Blood sugar control",
                "suggestion": "Focus on low glycemic index foods and consistent carb timing",
                "target": "Aim for 30-45g carbs per meal"
            })
        
        if "Hypertension" in medical_conditions:
            suggestions.append({
                "category": "Heart Health",
                "issue": "Blood pressure management",
                "suggestion": "Reduce sodium, increase potassium-rich foods like bananas and leafy greens",
                "target": "Less than 2,300mg sodium daily"
            })
        
        if dietary_category == "Vegan":
            suggestions.append({
                "category": "Plant-Based Nutrition",
                "issue": "Nutrient completeness",
                "suggestion": "Ensure B12, iron, and complete protein sources",
                "target": "Combine legumes with grains for complete proteins"
            })
        
        return suggestions

# Convenience function to create the agent
def create_food_intake_agent(authenticated_user_id: str = None):
    """Create and return a configured FoodIntakeAgent instance"""
    return FoodIntakeAgent(authenticated_user_id)