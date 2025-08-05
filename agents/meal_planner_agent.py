# agents/meal_planner_agent.py
from agno.agent import Agent
from agno.models.google import Gemini
from typing import Dict, Any, List, Optional
import sys
from dotenv import load_dotenv
import os

load_dotenv()
from datetime import datetime, timedelta

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from utils.database import DatabaseManager
from utils.client import GeminiClient

class MealPlannerAgent(Agent):
    def __init__(self, authenticated_user_id: str = None):
        super().__init__(
            name="MealPlannerAgent",
            model=Gemini(
            id=os.environ['DEFAULT_MODEL'],
            vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI'],
            project_id=os.environ['GOOGLE_CLOUD_PROJECT'],
            location=os.environ['GOOGLE_CLOUD_LOCATION'],
            api_key=os.environ.get('GOOGLE_API_KEY')),
            description="Generates personalized meal plans based on user preferences and health data",
            instructions=[
                "You are a certified nutritionist and meal planning specialist.",
                "Create personalized meal plans considering dietary preferences, medical conditions, mood, and CGM data.",
                "Ensure nutritional balance and variety in meal suggestions.",
                "Provide practical, achievable meal plans with clear portions.",
                "Consider budget-friendly and time-efficient options.",
                "Be encouraging and supportive in promoting healthy eating habits."
            ],
            show_tool_calls=True,
            markdown=True
        )
        self.db = DatabaseManager()
        self.llm_client = GeminiClient()
        self.authenticated_user_id = authenticated_user_id
        
        # Add custom tools
        self.add_tool(self.generate_meal_plan)
        self.add_tool(self.get_meal_plan_history)
        self.add_tool(self.customize_meal_plan)
        self.add_tool(self.get_shopping_list)
        self.add_tool(self.rate_meal_plan)
    
    def set_authenticated_user(self, user_id: str):
        """Set the authenticated user for this session"""
        self.authenticated_user_id = user_id
    
    def generate_meal_plan(self, plan_date: str = None, preferences: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate a personalized meal plan for a specific date
        
        Args:
            plan_date: Date for the meal plan (YYYY-MM-DD format, defaults to today)
            preferences: Optional additional preferences or restrictions
            
        Returns:
            Dict containing the generated meal plan
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to generate a meal plan."
            }
        
        if not plan_date:
            plan_date = datetime.now().strftime("%Y-%m-%d")
        
        # Get comprehensive user context
        user_context = self.db.get_user_context(self.authenticated_user_id)
        if not user_context:
            return {
                "status": "error",
                "message": "Unable to retrieve user information for meal planning."
            }
        
        # Log the interaction for tracking
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "MealPlannerAgent",
            "UserContext",
            "meal_planning",
            f"Generating meal plan for {plan_date} with {user_context['dietary_category']} diet"
        )
        
        # Add any additional preferences
        if preferences:
            user_context.update(preferences)
        
        # Enhance context with health insights
        enhanced_context = self._enhance_user_context_for_meal_planning(user_context)
        
        # Generate meal plan using LLM
        try:
            meal_plan = self.llm_client.generate_meal_plan(enhanced_context)
            
            # Validate and enhance the meal plan
            enhanced_plan = self._enhance_meal_plan(meal_plan, enhanced_context)
            
            # Store the meal plan
            self.db.store_meal_plan(self.authenticated_user_id, plan_date, enhanced_plan)
            
            # Generate presentation message
            message = self._format_meal_plan_message(enhanced_plan, enhanced_context, plan_date)
            
            return {
                "status": "success",
                "message": message,
                "meal_plan": enhanced_plan,
                "plan_date": plan_date,
                "user_context": {
                    "dietary_category": user_context["dietary_category"],
                    "medical_conditions": user_context["medical_conditions"],
                    "recent_mood_avg": user_context.get("recent_mood_avg"),
                    "recent_cgm_avg": user_context.get("recent_cgm_avg"),
                    "mood_trend": user_context.get("mood_trend"),
                    "cgm_trend": user_context.get("cgm_trend"),
                    "recent_calories_avg": user_context.get("recent_calories_avg")
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error generating meal plan: {str(e)}",
                "fallback_plan": self._generate_fallback_plan(user_context)
            }
    
    def get_meal_plan_history(self, days: int = 30) -> Dict[str, Any]:
        """
        Get meal plan history for the user
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dict containing meal plan history
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to view meal plan history."
            }
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            since_date = datetime.now() - timedelta(days=days)
            cursor.execute(
                """SELECT plan_date, breakfast, lunch, dinner, total_calories, 
                          total_carbs, total_protein, total_fat, created_at
                   FROM meal_plans 
                   WHERE user_id = ? AND created_at >= ?
                   ORDER BY plan_date DESC""",
                (self.authenticated_user_id, since_date.isoformat())
            )
            results = cursor.fetchall()
        
        if not results:
            return {
                "status": "success",
                "message": f"No meal plans found in the past {days} days.",
                "plans_count": 0
            }
        
        plans = []
        for row in results:
            plans.append({
                "plan_date": row[0],
                "breakfast": row[1],
                "lunch": row[2],
                "dinner": row[3],
                "total_calories": row[4],
                "total_carbs": row[5],
                "total_protein": row[6],
                "total_fat": row[7],
                "created_at": row[8]
            })
        
        # Calculate average nutrition
        avg_calories = sum(p["total_calories"] or 0 for p in plans) / len(plans)
        avg_carbs = sum(p["total_carbs"] or 0 for p in plans) / len(plans)
        avg_protein = sum(p["total_protein"] or 0 for p in plans) / len(plans)
        avg_fat = sum(p["total_fat"] or 0 for p in plans) / len(plans)
        
        return {
            "status": "success",
            "plans_count": len(plans),
            "plans": plans,
            "averages": {
                "calories": round(avg_calories, 1),
                "carbs": round(avg_carbs, 1),
                "protein": round(avg_protein, 1),
                "fat": round(avg_fat, 1)
            }
        }
    
    def customize_meal_plan(self, plan_date: str, customizations: Dict[str, str]) -> Dict[str, Any]:
        """
        Customize an existing meal plan or create a new one with specific requirements
        
        Args:
            plan_date: Date of the meal plan to customize
            customizations: Dict with meal replacements or specific requirements
            
        Returns:
            Dict containing the customized meal plan
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to customize meal plans."
            }
        
        # Get user context
        user_context = self.db.get_user_context(self.authenticated_user_id)
        
        # Apply customizations to context
        custom_context = user_context.copy()
        custom_context.update(customizations)
        
        # Add customization instructions
        custom_instructions = []
        if "avoid_foods" in customizations:
            custom_instructions.append(f"Avoid: {customizations['avoid_foods']}")
        if "include_foods" in customizations:
            custom_instructions.append(f"Must include: {customizations['include_foods']}")
        if "calorie_target" in customizations:
            custom_instructions.append(f"Target calories: {customizations['calorie_target']}")
        if "meal_prep" in customizations:
            custom_instructions.append("Focus on meal prep friendly options")
        
        custom_context["special_instructions"] = "; ".join(custom_instructions)
        
        # Generate customized meal plan
        try:
            meal_plan = self.llm_client.generate_meal_plan(custom_context)
            enhanced_plan = self._enhance_meal_plan(meal_plan, custom_context)
            
            # Store the customized plan
            self.db.store_meal_plan(self.authenticated_user_id, plan_date, enhanced_plan)
            
            message = f"✅ **Customized Meal Plan for {plan_date}**\n\n"
            message += self._format_meal_plan_message(enhanced_plan, custom_context, plan_date)
            
            if custom_instructions:
                message += f"\n\n**Applied Customizations:** {'; '.join(custom_instructions)}"
            
            return {
                "status": "success",
                "message": message,
                "meal_plan": enhanced_plan,
                "customizations_applied": custom_instructions
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error customizing meal plan: {str(e)}"
            }
    
    def get_shopping_list(self, plan_dates: List[str] = None) -> Dict[str, Any]:
        """
        Generate a shopping list based on meal plans
        
        Args:
            plan_dates: List of dates to include in shopping list (defaults to next 3 days)
            
        Returns:
            Dict containing organized shopping list
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to generate shopping lists."
            }
        
        if not plan_dates:
            # Default to next 3 days
            plan_dates = [
                (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(3)
            ]
        
        # Get meal plans for specified dates
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in plan_dates)
            cursor.execute(
                f"""SELECT plan_date, breakfast, lunch, dinner
                    FROM meal_plans 
                    WHERE user_id = ? AND plan_date IN ({placeholders})
                    ORDER BY plan_date""",
                [self.authenticated_user_id] + plan_dates
            )
            results = cursor.fetchall()
        
        if not results:
            return {
                "status": "success",
                "message": "No meal plans found for the specified dates. Generate meal plans first!",
                "shopping_list": {}
            }
        
        # Extract ingredients from meal descriptions
        all_meals = []
        for row in results:
            all_meals.extend([row[1], row[2], row[3]])  # breakfast, lunch, dinner
        
        # Use LLM to extract shopping list
        shopping_list = self._extract_shopping_list(all_meals)
        
        return {
            "status": "success",
            "message": f"Shopping list generated for {len(results)} meal plans",
            "shopping_list": shopping_list,
            "plan_dates": [row[0] for row in results]
        }
    
    def rate_meal_plan(self, plan_date: str, rating: int, feedback: str = "") -> Dict[str, Any]:
        """
        Rate a meal plan for future improvements
        
        Args:
            plan_date: Date of the meal plan to rate
            rating: Rating from 1-5 stars
            feedback: Optional feedback text
            
        Returns:
            Dict containing confirmation
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to rate meal plans."
            }
        
        if not 1 <= rating <= 5:
            return {
                "status": "error",
                "message": "Rating must be between 1 and 5 stars."
            }
        
        # Store rating (you might want to add a ratings table to your database)
        # For now, we'll just acknowledge the rating
        
        rating_text = "⭐" * rating + "☆" * (5 - rating)
        message = f"✅ Thank you for rating the meal plan for {plan_date}!\n\n"
        message += f"**Rating:** {rating_text} ({rating}/5)\n"
        
        if feedback:
            message += f"**Feedback:** {feedback}\n"
        
        message += "\nYour feedback helps us improve future meal recommendations!"
        
        return {
            "status": "success",
            "message": message,
            "rating": rating,
            "plan_date": plan_date
        }
    
    def _enhance_meal_plan(self, meal_plan: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance and validate the generated meal plan"""
        enhanced = meal_plan.copy()
        
        # Ensure all required fields exist
        required_fields = ["breakfast", "lunch", "dinner", "total_calories", "total_carbs", "total_protein", "total_fat"]
        for field in required_fields:
            if field not in enhanced:
                enhanced[field] = 0 if "total_" in field else "Not specified"
        
        # Add nutritional recommendations based on conditions
        recommendations = []
        medical_conditions = user_context.get("medical_conditions", [])
        
        if any(condition in medical_conditions for condition in ["Type 1 Diabetes", "Type 2 Diabetes"]):
            recommendations.append("Monitor blood glucose after meals")
            recommendations.append("Consider the carb content timing with medication")
        
        if "Hypertension" in medical_conditions:
            recommendations.append("Watch sodium content in processed foods")
        
        if user_context.get("recent_mood_avg", 5) < 4:
            recommendations.append("Include mood-boosting foods like omega-3 rich fish")
        
        enhanced["recommendations"] = recommendations
        enhanced["generated_for"] = user_context.get("name", "User")
        
        return enhanced
    
    def _enhance_user_context_for_meal_planning(self, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance user context with health insights for better meal planning"""
        enhanced = user_context.copy()
        
        # Add mood-based recommendations
        mood_avg = user_context.get("recent_mood_avg", 5)
        mood_trend = user_context.get("mood_trend", "stable")
        
        if mood_avg < 4:
            enhanced["mood_considerations"] = [
                "Include mood-boosting foods rich in omega-3 fatty acids",
                "Add foods high in tryptophan (turkey, nuts, seeds)",
                "Include complex carbohydrates for serotonin production",
                "Consider warm, comforting foods"
            ]
        elif mood_avg > 7:
            enhanced["mood_considerations"] = [
                "Maintain energy with balanced meals",
                "Include foods that support sustained energy",
                "Focus on nutrient-dense options"
            ]
        
        # Add CGM-based recommendations
        cgm_avg = user_context.get("recent_cgm_avg", 0)
        cgm_trend = user_context.get("cgm_trend", "stable")
        
        if cgm_avg > 180:
            enhanced["glucose_considerations"] = [
                "Focus on low glycemic index foods",
                "Include more fiber-rich vegetables",
                "Limit simple carbohydrates",
                "Consider meal timing with medication"
            ]
        elif cgm_avg < 80:
            enhanced["glucose_considerations"] = [
                "Include moderate amounts of complex carbohydrates",
                "Ensure regular meal timing",
                "Include protein with each meal"
            ]
        
        # Add nutrition-based recommendations
        recent_calories = user_context.get("recent_calories_avg", 0)
        recent_carbs = user_context.get("recent_carbs_avg", 0)
        recent_protein = user_context.get("recent_protein_avg", 0)
        
        if recent_calories > 0:
            if recent_calories < 1200:
                enhanced["calorie_considerations"] = ["Increase portion sizes", "Add healthy snacks"]
            elif recent_calories > 2500:
                enhanced["calorie_considerations"] = ["Focus on nutrient density", "Reduce portion sizes"]
            
            if recent_protein < 60:
                enhanced["protein_considerations"] = ["Increase protein sources", "Include protein with each meal"]
            
            if recent_carbs > 300:
                enhanced["carb_considerations"] = ["Reduce simple carbohydrates", "Focus on complex carbs"]
        
        # Add medical condition considerations
        medical_conditions = user_context.get("medical_conditions", [])
        enhanced["medical_considerations"] = []
        
        for condition in medical_conditions:
            if "Diabetes" in condition:
                enhanced["medical_considerations"].extend([
                    "Monitor carbohydrate content",
                    "Consider glycemic index",
                    "Include protein with carbohydrates"
                ])
            elif "Hypertension" in condition:
                enhanced["medical_considerations"].extend([
                    "Limit sodium content",
                    "Include potassium-rich foods",
                    "Focus on heart-healthy fats"
                ])
            elif "High Cholesterol" in condition:
                enhanced["medical_considerations"].extend([
                    "Limit saturated fats",
                    "Include soluble fiber",
                    "Focus on plant-based proteins"
                ])
        
        return enhanced
    
    def _format_meal_plan_message(self, meal_plan: Dict[str, Any], user_context: Dict[str, Any], plan_date: str) -> str:
        """Format the meal plan into a readable message"""
        message = f"🍽️ **Personalized Meal Plan for {plan_date}**\n\n"
        
        # User context summary
        message += f"**Planned for:** {user_context.get('name', 'User')} ({user_context['dietary_category']})\n"
        if user_context.get('recent_mood_avg'):
            message += f"**Recent Mood:** {user_context['recent_mood_avg']:.1f}/10\n"
        if user_context.get('recent_cgm_avg'):
            message += f"**Recent CGM:** {user_context['recent_cgm_avg']:.1f} mg/dL\n"
        message += "\n"
        
        # Meals
        message += f"🌅 **Breakfast:**\n{meal_plan['breakfast']}\n\n"
        message += f"🌞 **Lunch:**\n{meal_plan['lunch']}\n\n"
        message += f"🌙 **Dinner:**\n{meal_plan['dinner']}\n\n"
        
        # Nutrition summary
        message += "📊 **Daily Nutrition Summary:**\n"
        message += f"• Total Calories: {meal_plan.get('total_calories', 'N/A')} kcal\n"
        message += f"• Carbohydrates: {meal_plan.get('total_carbs', 'N/A')}g\n"
        message += f"• Protein: {meal_plan.get('total_protein', 'N/A')}g\n"
        message += f"• Fat: {meal_plan.get('total_fat', 'N/A')}g\n\n"
        
        # Recommendations
        if meal_plan.get("recommendations"):
            message += "💡 **Health Recommendations:**\n"
            for rec in meal_plan["recommendations"]:
                message += f"• {rec}\n"
            message += "\n"
        
        # Notes
        if meal_plan.get("notes"):
            message += f"📝 **Notes:** {meal_plan['notes']}\n"
        
        return message
    
    def _generate_fallback_plan(self, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a simple fallback meal plan"""
        dietary = user_context.get("dietary_category", "Standard").lower()
        
        if "vegan" in dietary:
            return {
                "breakfast": "Overnight oats with almond milk, chia seeds, and berries",
                "lunch": "Quinoa salad with chickpeas, vegetables, and tahini dressing",
                "dinner": "Lentil curry with brown rice and steamed vegetables",
                "total_calories": 1600,
                "total_carbs": 220,
                "total_protein": 60,
                "total_fat": 45,
                "notes": "Plant-based meals rich in fiber and protein"
            }
        else:
            return {
                "breakfast": "Greek yogurt with granola and fresh fruit",
                "lunch": "Grilled chicken salad with mixed greens and olive oil",
                "dinner": "Baked salmon with roasted vegetables and quinoa",
                "total_calories": 1500,
                "total_carbs": 150,
                "total_protein": 100,
                "total_fat": 55,
                "notes": "Balanced meals with lean protein and vegetables"
            }
    
    def _extract_shopping_list(self, meals: List[str]) -> Dict[str, List[str]]:
        """Extract shopping list from meal descriptions using LLM"""
        meals_text = "\n".join(meals)
        
        prompt = f"""
        Extract a shopping list from these meal descriptions. Organize by category:
        
        Meals:
        {meals_text}
        
        Provide response in this JSON format:
        {{
            "proteins": ["item1", "item2"],
            "vegetables": ["item1", "item2"],
            "fruits": ["item1", "item2"],
            "grains": ["item1", "item2"],
            "dairy": ["item1", "item2"],
            "pantry": ["item1", "item2"]
        }}
        
        Only include actual ingredients, not prepared dishes. Only respond with JSON.
        """
        
        try:
            response = self.llm_client.generate_response(prompt)
            import json
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = response[start:end]
                return json.loads(json_str)
            else:
                return self._fallback_shopping_list()
        except:
            return self._fallback_shopping_list()
    
    def _fallback_shopping_list(self) -> Dict[str, List[str]]:
        """Fallback shopping list if LLM extraction fails"""
        return {
            "proteins": ["chicken breast", "salmon", "eggs", "Greek yogurt"],
            "vegetables": ["mixed greens", "broccoli", "bell peppers", "onions"],
            "fruits": ["berries", "bananas", "apples"],
            "grains": ["quinoa", "brown rice", "oats"],
            "dairy": ["milk", "cheese"],
            "pantry": ["olive oil", "spices", "nuts", "seeds"]
        }

# Convenience function to create the agent
def create_meal_planner_agent(authenticated_user_id: str = None):
    return MealPlannerAgent(authenticated_user_id)