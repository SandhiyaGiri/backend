# main.py - Health Agent System Orchestrator
import os
import sys
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import all agents
from agents.greeting_agent import create_greeting_agent
from agents.cgm_agent import create_cgm_agent
from agents.mood_tracker_agent import create_mood_tracker_agent
from agents.food_intake_agent import create_food_intake_agent
from agents.meal_planner_agent import create_meal_planner_agent
from agents.interrupt_agent import create_interrupt_agent
from utils.database import DatabaseManager

class HealthAgentSystem:
    def __init__(self):
        """Initialize the multi-agent health system"""
        self.authenticated_user_id = None
        self.current_user_name = None
        
        # Initialize database manager
        self.db = DatabaseManager()
        
        # Initialize agents
        self.greeting_agent = create_greeting_agent()
        self.interrupt_agent = create_interrupt_agent()
        
        # These will be initialized after authentication
        self.cgm_agent = None
        self.mood_tracker_agent = None
        self.food_intake_agent = None
        self.meal_planner_agent = None
        
        self.system_state = "unauthenticated"  # unauthenticated, authenticated, active
        
    def _initialize_authenticated_agents(self):
        """Initialize agents that require authentication"""
        if self.authenticated_user_id:
            self.cgm_agent = create_cgm_agent(self.authenticated_user_id)
            self.mood_tracker_agent = create_mood_tracker_agent(self.authenticated_user_id)
            self.food_intake_agent = create_food_intake_agent(self.authenticated_user_id)
            self.meal_planner_agent = create_meal_planner_agent(self.authenticated_user_id)
            self.interrupt_agent.set_authenticated_user(self.authenticated_user_id)
    
    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input and route to appropriate agent
        
        Args:
            user_input: Raw user input string
            
        Returns:
            Dict containing response and system state information
        """
        user_input = user_input.strip()
        
        if not user_input:
            return {
                "response": "Please enter a message!",
                "agent_used": None,
                "system_state": self.system_state
            }
        
        # Handle authentication first
        if self.system_state == "unauthenticated":
            return self._handle_authentication(user_input)
        
        # Route to appropriate agent based on intent
        return self._route_authenticated_request(user_input)
    
    def _handle_authentication(self, user_input: str) -> Dict[str, Any]:
        """Handle user authentication flow"""
        
        # Check if user is trying to provide a user ID
        if self._looks_like_user_id(user_input):
            result = self.greeting_agent.validate_user_id(user_input)
            
            if result["status"] == "success":
                self.authenticated_user_id = user_input
                self.current_user_name = result["user_data"]["name"]
                self.current_user_location = result["user_data"]["city"]
                self.system_state = "authenticated"
                self._initialize_authenticated_agents()
                
                welcome_message = f"""🎉 **Welcome back, {self.current_user_name} from {self.current_user_location}!**

I'm your personal health assistant. Here's what I can help you with today:

**🏥 Quick Actions:**
• **Track Mood** - "I'm feeling great today!"
• **Log Glucose** - "My glucose reading is 120"
• **Log Food** - "I ate grilled chicken with vegetables"
• **Plan Meals** - "Generate a meal plan for tomorrow"
• **Get Insights** - "Show me my mood trends"

**❓ Need Help?**
• Ask me anything about health and nutrition
• Say "help" or "what can you do?" for more options
• Type "features" to see all available tools

What would you like to do first?"""
                
                return {
                    "response": welcome_message,
                    "agent_used": "GreetingAgent",
                    "system_state": self.system_state,
                    "user_authenticated": True
                }
            else:
                # Invalid user ID - offer to help find it
                search_message = result["message"] + "\n\n💡 **Can't find your ID?** Tell me your name and I'll help you find it!\nExample: 'My name is John Smith'"
                return {
                    "response": search_message,
                    "agent_used": "GreetingAgent",
                    "system_state": self.system_state
                }
        
        # Check if user is providing their name for ID lookup
        elif self._looks_like_name_search(user_input):
            name = self._extract_name_from_input(user_input)
            result = self.greeting_agent.search_users_by_name(name)
            
            if result["status"] == "success":
                users = result["users"]
                if len(users) == 1:
                    # Single match - ask for confirmation
                    user = users[0]
                    confirm_message = f"""✅ **Found a match!**
                    
**Name:** {user['name']}
**Location:** {user['city']}`

Is this you? If yes, type your User ID to log in."""
                    
                    return {
                        "response": confirm_message,
                        "agent_used": "GreetingAgent",
                        "system_state": self.system_state,
                        "suggested_user_id": user['user_id']
                    }
                else:
                    # Multiple matches
                    matches_text = "\n".join([f"• **{u['name']}** ({u['city']}) - ID: `{u['user_id']}`" for u in users])
                    multiple_message = f"""📋 **Found {len(users)} matches for '{name}':**

{matches_text}

Please copy and paste the correct User ID to log in."""
                    
                    return {
                        "response": multiple_message,
                        "agent_used": "GreetingAgent",
                        "system_state": self.system_state
                    }
            else:
                return {
                    "response": result["message"] + "\n\nTry a different spelling or ask for help finding your account.",
                    "agent_used": "GreetingAgent",
                    "system_state": self.system_state
                }
        
        # General help or other input while unauthenticated
        else:
            help_message = """👋 **Welcome to your Personal Health Assistant!**

To get started, I need to verify your identity:

**🔐 Login Options:**
1. **Enter your User ID** - If you know your unique user ID
2. **Tell me your name** - Say "My name is [Your Name]" and I'll help find your ID

**❓ Don't have an account?**
This system uses the synthetic health database. Check with your administrator for access.

**💡 Example:**
• "My name is John Smith" 
• Or paste your User ID directly

How would you like to proceed?"""
            
            return {
                "response": help_message,
                "agent_used": "GreetingAgent",
                "system_state": self.system_state
            }
    
    def _route_authenticated_request(self, user_input: str) -> Dict[str, Any]:
        """Route requests for authenticated users"""
        input_lower = user_input.lower()
        
        # System commands
        if input_lower in ["help", "features", "what can you do", "options"]:
            result = self.interrupt_agent.explain_system_features()
            return {
                "response": result["explanation"],
                "agent_used": "InterruptAgent",
                "system_state": self.system_state
            }
        
        if input_lower in ["logout", "sign out", "exit"]:
            return self._handle_logout()
        
        # Detect intent and route to appropriate agent
        intent = self._detect_primary_intent(user_input)
        
        try:
            if intent == "mood_tracking":
                return self._handle_mood_tracking(user_input)
            elif intent == "cgm_monitoring":
                return self._handle_cgm_monitoring(user_input)
            elif intent == "food_logging":
                return self._handle_food_logging(user_input)
            elif intent == "meal_planning":
                return self._handle_meal_planning(user_input)
            elif intent == "insights_request":
                return self._handle_insights_request(user_input)
            else:
                # General Q&A or unclear intent
                return self._handle_general_question(user_input)
        
        except Exception as e:
            return {
                "response": f"❌ Sorry, I encountered an error: {str(e)}\n\nPlease try again or ask for help.",
                "agent_used": "SystemError",
                "system_state": self.system_state
            }
    
    def _handle_meal_planning(self, user_input: str) -> Dict[str, Any]:
        """Handle meal planning requests"""
        plan_date = self._extract_date_from_input(user_input)
        
        # Get comprehensive user context for meal planning
        user_context = self.db.get_user_context(self.authenticated_user_id)
        
        # Log cross-agent interaction
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "MainSystem",
            "MealPlannerAgent",
            "meal_planning_request",
            f"Requesting meal plan for {plan_date} with context: {user_context['dietary_category']} diet"
        )
        
        result = self.meal_planner_agent.generate_meal_plan(plan_date)
        
        return {
            "response": result["message"],
            "agent_used": "MealPlannerAgent",
            "system_state": self.system_state,
            "data_generated": "meal_plan",
            "user_context_used": {
                "dietary_category": user_context["dietary_category"],
                "medical_conditions": user_context["medical_conditions"],
                "recent_mood_avg": user_context.get("recent_mood_avg"),
                "recent_cgm_avg": user_context.get("recent_cgm_avg"),
                "mood_trend": user_context.get("mood_trend"),
                "cgm_trend": user_context.get("cgm_trend")
            }
        }
    
    def _handle_mood_tracking(self, user_input: str) -> Dict[str, Any]:
        """Handle mood tracking requests"""
        mood_label = self._extract_mood_from_input(user_input)
        
        # Log cross-agent interaction
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "MainSystem",
            "MoodTrackerAgent",
            "mood_logging_request",
            f"Logging mood: {mood_label}"
        )
        
        result = self.mood_tracker_agent.log_mood(mood_label)
        
        return {
            "response": result["message"],
            "agent_used": "MoodTrackerAgent",
            "system_state": self.system_state,
            "data_logged": "mood",
            "mood_score": result.get("mood_score"),
            "recommendations": result.get("recommendations")
        }
    
    def _handle_cgm_monitoring(self, user_input: str) -> Dict[str, Any]:
        """Handle CGM monitoring requests"""
        glucose_reading = self._extract_glucose_reading(user_input)
        
        if glucose_reading is None:
            return {
                "response": "I couldn't find a glucose reading in your message. Please include the number, like 'My glucose is 120' or '125 mg/dL'",
                "agent_used": "CGMAgent",
                "system_state": self.system_state
            }
        
        # Log cross-agent interaction
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "MainSystem",
            "CGMAgent",
            "glucose_logging_request",
            f"Logging glucose reading: {glucose_reading} mg/dL"
        )
        
        result = self.cgm_agent.process_glucose_reading(glucose_reading)
        
        return {
            "response": result["message"],
            "agent_used": "CGMAgent",
            "system_state": self.system_state,
            "data_logged": "glucose",
            "alert_type": result.get("alert_type"),
            "recommendations": result.get("recommendations")
        }
    
    def _handle_food_logging(self, user_input: str) -> Dict[str, Any]:
        """Handle food logging requests"""
        meal_description = self._extract_meal_description(user_input)
        
        # Log cross-agent interaction
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "MainSystem",
            "FoodIntakeAgent",
            "food_logging_request",
            f"Logging meal: {meal_description[:50]}..."
        )
        
        result = self.food_intake_agent.log_meal(meal_description)
        
        return {
            "response": result["message"],
            "agent_used": "FoodIntakeAgent",
            "system_state": self.system_state,
            "data_logged": "food",
            "nutrients": result.get("nutrients"),
            "context_feedback": result.get("context_feedback")
        }
    
    def _handle_insights_request(self, user_input: str) -> Dict[str, Any]:
        """Handle requests for insights and trends"""
        input_lower = user_input.lower()
        
        # Get comprehensive health summary
        health_summary = self.db.get_health_summary(self.authenticated_user_id)
        
        if "mood" in input_lower:
            result = self.mood_tracker_agent.get_mood_trends()
            return {
                "response": f"📊 **Mood Trends:**\n\n{self._format_mood_trends(result)}",
                "agent_used": "MoodTrackerAgent",
                "system_state": self.system_state
            }
        
        elif "glucose" in input_lower or "cgm" in input_lower:
            result = self.cgm_agent.get_glucose_trends()
            return {
                "response": f"📈 **Glucose Trends:**\n\n{self._format_glucose_trends(result)}",
                "agent_used": "CGMAgent",
                "system_state": self.system_state
            }
        
        elif "nutrition" in input_lower or "food" in input_lower:
            result = self.food_intake_agent.get_nutrition_insights()
            return {
                "response": f"🥗 **Nutrition Insights:**\n\n{self._format_nutrition_insights(result)}",
                "agent_used": "FoodIntakeAgent",
                "system_state": self.system_state
            }
        
        else:
            # General insights summary with cross-agent data
            return self._generate_comprehensive_insights()
    
    def _handle_general_question(self, user_input: str) -> Dict[str, Any]:
        """Handle general questions and route appropriately"""
        result = self.interrupt_agent.answer_general_question(user_input)
        response = result["answer"]
        
        # Use the improved routing suggestion from the interrupt agent
        routing_suggestion = result.get("routing_suggestion")
        
        # If no specific routing from the new logic, fall back to the old routing
        if not routing_suggestion:
            routing = self.interrupt_agent.route_to_appropriate_agent(user_input)
            if routing.get("routing_suggestion"):
                response += f"\n\n🔄 **Suggestion:** {routing['message']}"
                routing_suggestion = routing.get("recommended_agent")
        
        return {
            "response": response,
            "agent_used": "InterruptAgent",
            "system_state": self.system_state,
            "routing_suggestion": routing_suggestion
        }
    
    def _handle_logout(self) -> Dict[str, Any]:
        """Handle user logout"""
        user_name = self.current_user_name
        
        # Reset system state
        self.authenticated_user_id = None
        self.current_user_name = None
        self.system_state = "unauthenticated"
        
        # Clear authenticated agents
        self.cgm_agent = None
        self.mood_tracker_agent = None
        self.food_intake_agent = None
        self.meal_planner_agent = None
        
        return {
            "response": f"👋 Goodbye, {user_name}! You've been successfully logged out.\n\nTo log back in, just provide your User ID or name when you're ready.",
            "agent_used": "GreetingAgent",
            "system_state": self.system_state,
            "user_logged_out": True
        }
    
    def _detect_primary_intent(self, user_input: str) -> str:
        """Detect the primary intent from user input with enhanced pattern recognition"""
        import re
        input_lower = user_input.lower().strip()
        
        # Enhanced mood tracking patterns
        mood_indicators = {
            # Direct mood words
            "direct": ["feel", "mood", "feeling", "emotions", "emotional"],
            # Positive mood expressions
            "positive": ["happy", "great", "awesome", "fantastic", "wonderful", "excited", "thrilled", "amazing", "good", "better", "cheerful", "joyful", "elated", "ecstatic"],
            # Negative mood expressions  
            "negative": ["sad", "terrible", "awful", "horrible", "bad", "worse", "depressed", "down", "low", "upset", "angry", "frustrated", "stressed", "anxious", "worried", "scared", "tired", "exhausted", "drained"],
            # Self-referential mood statements
            "self_ref": ["i am", "i'm", "i feel", "i'm feeling", "feeling", "today i", "right now i"],
            # Mood qualifiers
            "qualifiers": ["really", "very", "extremely", "super", "so", "quite", "pretty", "kind of", "sort of", "a bit", "little"]
        }
        
        # CGM monitoring patterns  
        cgm_indicators = {
            "direct": ["glucose", "blood sugar", "cgm", "reading", "mg/dl", "sugar level", "diabetes", "diabetic"],
            "values": [r'\d+\s*(?:mg|glucose|sugar|reading)', r'glucose.*\d+', r'sugar.*\d+', r'reading.*\d+'],
            "actions": ["check", "test", "measure", "monitor"]
        }
        
        # Enhanced food logging patterns
        food_indicators = {
            "past_tense": ["ate", "had", "eaten", "consumed", "finished", "devoured"],
            "present_tense": ["eating", "having", "consuming"],
            "meals": ["breakfast", "lunch", "dinner", "snack", "meal", "brunch", "supper"],
            "food_items": ["food", "pizza", "salad", "chicken", "rice", "bread", "fruit", "vegetables"],
            "context": ["just", "recently", "earlier", "this morning", "for lunch", "for dinner"]
        }
        
        # Meal planning patterns
        planning_indicators = {
            "direct": ["meal plan", "plan meal", "plan a meal", "meal planning", "menu", "meal ideas", "suggest meals", "what to eat", "plan my meals"],
            "planning_verbs": ["plan", "planning", "suggest", "recommend", "generate", "create"],
            "questions": ["what should i eat", "what can i eat", "meal suggestions", "food recommendations"],
            "time_based": ["tomorrow", "today", "this week", "next week", "meal prep"]
        }
        
        # Insights patterns
        insights_indicators = {
            "direct": ["trends", "insights", "show me", "view", "display", "analysis", "patterns", "summary", "report", "data", "statistics", "dashboard"],
            "requests": ["how am i doing", "my progress", "track my", "history", "overview", "my health", "health dashboard"]
        }
        
        # Check for glucose readings with numbers
        for pattern in cgm_indicators["values"]:
            if re.search(pattern, input_lower):
                return "cgm_monitoring"
        
        # Enhanced scoring system
        def calculate_mood_score():
            score = 0
            # Direct mood references
            score += sum(2 for word in mood_indicators["direct"] if word in input_lower)
            score += sum(2 for word in mood_indicators["positive"] if word in input_lower)
            score += sum(2 for word in mood_indicators["negative"] if word in input_lower)
            
            # Self-referential statements (strong mood indicators)
            for phrase in mood_indicators["self_ref"]:
                if phrase in input_lower:
                    score += 3
                    
            # Look for emotional context patterns
            # "I'm stupid" -> mood tracking
            if re.search(r"i'?m\s+(stupid|dumb|worthless|useless|terrible|awful|pathetic)", input_lower):
                score += 5
            # "I feel like..." -> mood tracking  
            if re.search(r"i\s+feel\s+like", input_lower):
                score += 4
            # Emotional self-descriptions
            if re.search(r"i'?m\s+(so|really|very|extremely)\s+\w+", input_lower):
                score += 3
                
            return score
        
        def calculate_cgm_score():
            score = 0
            score += sum(2 for word in cgm_indicators["direct"] if word in input_lower)
            score += sum(1 for word in cgm_indicators["actions"] if word in input_lower)
            return score
        
        def calculate_food_score():
            score = 0
            score += sum(3 for word in food_indicators["past_tense"] if word in input_lower)
            score += sum(2 for word in food_indicators["present_tense"] if word in input_lower)
            score += sum(1 for word in food_indicators["food_items"] if word in input_lower)
            score += sum(1 for word in food_indicators["context"] if word in input_lower)
            
            # Only give points for meal words if they're in logging context
            has_logging_context = any(word in input_lower for word in food_indicators["past_tense"] + food_indicators["context"])
            has_planning_context = any(verb in input_lower for verb in planning_indicators["planning_verbs"])
            
            if not has_planning_context and has_logging_context:
                score += sum(2 for word in food_indicators["meals"] if word in input_lower)
            elif not has_planning_context:
                score += sum(1 for word in food_indicators["meals"] if word in input_lower)
            
            return score
        
        def calculate_planning_score():
            score = 0
            score += sum(4 for phrase in planning_indicators["direct"] if phrase in input_lower)
            score += sum(2 for phrase in planning_indicators["questions"] if phrase in input_lower)
            score += sum(1 for phrase in planning_indicators["time_based"] if phrase in input_lower)
            
            # Check for planning verbs combined with meal-related words
            planning_verbs_present = any(verb in input_lower for verb in planning_indicators["planning_verbs"])
            meal_words_present = any(meal in input_lower for meal in ["meal", "menu", "food", "diet"])
            
            if planning_verbs_present and meal_words_present:
                score += 5  # Strong indicator of meal planning
            elif planning_verbs_present:
                score += 2  # Planning context
                
            return score
        
        def calculate_insights_score():
            score = 0
            score += sum(2 for word in insights_indicators["direct"] if word in input_lower)
            score += sum(2 for phrase in insights_indicators["requests"] if phrase in input_lower)
            
            # Boost score for "show" or "view" commands
            if any(word in input_lower for word in ["show", "view", "display", "get"]):
                score += 5
            
            return score
        
        # Calculate scores
        scores = {
            "mood_tracking": calculate_mood_score(),
            "cgm_monitoring": calculate_cgm_score(),
            "food_logging": calculate_food_score(),
            "meal_planning": calculate_planning_score(),
            "insights_request": calculate_insights_score()
        }
        
        max_score = max(scores.values())
        if max_score > 0:
            return max(scores, key=scores.get)
        
        return "general_question"
    
    def _looks_like_user_id(self, text: str) -> bool:
        """Check if text looks like a user ID"""
        import re
        # Support 4-digit numeric user IDs, UUIDs or similar patterns
        return bool(
            re.match(r'^\d{4}$', text) or  # 4-digit numeric user IDs
            re.match(r'^[a-f0-9-]{8,}$', text.lower()) or 
            re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', text.lower())
        )

    
    def _looks_like_name_search(self, text: str) -> bool:
        """Check if text looks like a name search"""
        return any(phrase in text.lower() for phrase in [
            "my name is", "i am", "name:", "called", "i'm"
        ])
    
    def _extract_name_from_input(self, text: str) -> str:
        """Extract name from user input"""
        import re
        
        # Try different patterns
        patterns = [
            r"my name is (.+)",
            r"i am (.+)",
            r"name:?\s*(.+)",
            r"called (.+)",
            r"i'm (.+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(1).strip()
        
        # Fallback - assume the whole input is a name
        return text.strip()
    
    def _extract_mood_from_input(self, text: str) -> str:
        """Extract mood description from user input"""
        # Remove common prefixes
        prefixes = ["i feel", "i'm feeling", "feeling", "i am", "mood:", "my mood is"]
        
        text_lower = text.lower()
        for prefix in prefixes:
            if text_lower.startswith(prefix):
                return text[len(prefix):].strip()
        
        return text.strip()
    


    def _extract_glucose_reading(self, text: str) -> Optional[float]:
        """Extract glucose reading from user input"""
        import re

        # Look for numbers followed by optional units or contextual words
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:mg/dl|mg|glucose|reading)',  # Number with unit
            r'glucose.*?(\d+(?:\.\d+)?)',                       # "glucose" before number
            r'reading.*?(\d+(?:\.\d+)?)',                       # "reading" before number
            r'sugar.*?(\d+(?:\.\d+)?)',                         # "sugar" before number
            r'(\d+(?:\.\d+)?)'                                  # Any number
        ]

        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        return None

    
    def _extract_meal_description(self, text: str) -> str:
        """Extract meal description from user input"""
        # Remove common prefixes
        prefixes = [
            "i ate", "i had", "just ate", "just had", "meal:", "food:", 
            "consumed", "eaten", "my meal was", "for lunch i had",
            "for dinner i had", "for breakfast i had"
        ]
        
        text_lower = text.lower()
        for prefix in prefixes:
            if text_lower.startswith(prefix):
                return text[len(prefix):].strip()
        
        return text.strip()
    
    def _extract_date_from_input(self, text: str) -> Optional[str]:
        """Extract date from user input"""
        import re
        from datetime import datetime, timedelta
        
        text_lower = text.lower()
        
        # Handle relative dates
        if "today" in text_lower:
            return datetime.now().strftime("%Y-%m-%d")
        elif "tomorrow" in text_lower:
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "yesterday" in text_lower:
            return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Look for specific date patterns
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY
            r'(\d{1,2}-\d{1,2}-\d{4})'   # MM-DD-YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                try:
                    # Convert to standard format
                    if '/' in date_str:
                        month, day, year = date_str.split('/')
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    elif '-' in date_str and len(date_str.split('-')[0]) <= 2:
                        month, day, year = date_str.split('-')
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:
                        return date_str  # Already in YYYY-MM-DD format
                except:
                    continue
        
        # Default to today if no date found
        return None
    
    def _format_mood_trends(self, result: Dict[str, Any]) -> str:
        """Format mood trends for display"""
        if result["entries_count"] == 0:
            return "No mood entries found. Start logging your mood daily to see trends!"
        
        text = f"**Entries:** {result['entries_count']} in the past month\n"
        text += f"**Average Mood:** {result['average_mood']}/10\n"
        text += f"**Range:** {result['min_mood']}-{result['max_mood']}/10\n"
        text += f"**Trend:** {result['trend'].replace('_', ' ').title()}\n\n"
        
        if result.get('common_moods'):
            text += "**Most Common Moods:**\n"
            for mood, count in result['common_moods'][:3]:
                text += f"• {mood.title()}: {count} times\n"
        
        return text
    
    def _format_glucose_trends(self, result: Dict[str, Any]) -> str:
        """Format glucose trends for display"""
        if result["readings_count"] == 0:
            return "No glucose readings found. Start logging readings to see trends!"
        
        text = f"**Readings:** {result['readings_count']} in the past week\n"
        text += f"**Average:** {result['average_glucose']} mg/dL\n"
        text += f"**Range:** {result['min_glucose']}-{result['max_glucose']} mg/dL\n"
        text += f"**Time in Range:** {result['time_in_range']}%\n"
        text += f"**Target Range:** {result['target_range']}\n"
        text += f"**Trend:** {result['trend'].replace('_', ' ').title()}\n"
        
        return text
    
    def _format_nutrition_insights(self, result: Dict[str, Any]) -> str:
        """Format nutrition insights for display"""
        if result["days_analyzed"] == 0:
            return "No nutrition data found. Start logging meals to see insights!"
        
        averages = result["averages"]
        text = f"**Days Analyzed:** {result['days_analyzed']}\n"
        text += f"**Daily Averages:**\n"
        text += f"• Calories: {averages['calories']} kcal\n"
        text += f"• Carbs: {averages['carbs']}g\n"
        text += f"• Protein: {averages['protein']}g\n"
        text += f"• Fat: {averages['fat']}g\n"
        text += f"• Meals per day: {averages['meals_per_day']}\n\n"
        
        if result.get("patterns"):
            text += "**Patterns:**\n"
            for pattern in result["patterns"]:
                text += f"• {pattern}\n"
        
        return text
    
    def _generate_comprehensive_insights(self) -> Dict[str, Any]:
        """Generate comprehensive insights across all health data"""
        health_summary = self.db.get_health_summary(self.authenticated_user_id)
        
        if not health_summary:
            return {
                "response": "Unable to retrieve health data. Please log in first.",
                "agent_used": "SystemInsights",
                "system_state": self.system_state
            }
        
        user_info = health_summary["user_info"]
        mood_summary = health_summary["mood_summary"]
        glucose_summary = health_summary["glucose_summary"]
        nutrition_summary = health_summary["nutrition_summary"]
        
        # Generate cross-agent insights
        cross_agent_insights = self._generate_cross_agent_insights(health_summary)
        
        summary = f"📊 **Comprehensive Health Summary for {user_info['name']}**\n\n"
        
        # User context
        summary += f"**👤 Profile:** {user_info['dietary_category']} diet\n"
        if user_info['medical_conditions']:
            summary += f"**🏥 Conditions:** {', '.join(user_info['medical_conditions'])}\n"
        summary += "\n"
        
        # Health metrics
        if mood_summary["entries_count"] > 0:
            trend_emoji = "📈" if mood_summary["trend"] == "improving" else "📉" if mood_summary["trend"] == "declining" else "➡️"
            summary += f"😊 **Mood:** {mood_summary['average']}/10 average {trend_emoji} ({mood_summary['entries_count']} entries)\n"
        
        if glucose_summary["readings_count"] > 0:
            trend_emoji = "📈" if glucose_summary["trend"] == "increasing" else "📉" if glucose_summary["trend"] == "decreasing" else "➡️"
            summary += f"🩸 **Glucose:** {glucose_summary['average']} mg/dL average {trend_emoji} ({glucose_summary['readings_count']} readings)\n"
        
        if nutrition_summary["entries_count"] > 0:
            summary += f"🍽️ **Nutrition:** {nutrition_summary['average_calories']:.0f} kcal/day average ({nutrition_summary['entries_count']} meals)\n"
        
        # Cross-agent insights
        if cross_agent_insights:
            summary += f"\n💡 **Cross-Agent Insights:**\n"
            for insight in cross_agent_insights:
                summary += f"• {insight}\n"
        
        summary += "\n**🔍 Quick Actions:**\n"
        summary += "• 'Show mood trends' for detailed mood analysis\n"
        summary += "• 'Show glucose trends' for CGM insights\n"
        summary += "• 'Show nutrition insights' for dietary analysis\n"
        summary += "• 'Generate meal plan' for tomorrow's meals\n"
        
        return {
            "response": summary,
            "agent_used": "SystemInsights",
            "system_state": self.system_state,
            "cross_agent_insights": cross_agent_insights
        }
    
    def _generate_cross_agent_insights(self, health_summary: Dict[str, Any]) -> List[str]:
        """Generate insights based on correlations between different health metrics"""
        insights = []
        
        mood_summary = health_summary["mood_summary"]
        glucose_summary = health_summary["glucose_summary"]
        nutrition_summary = health_summary["nutrition_summary"]
        
        # Mood and glucose correlation
        if mood_summary["entries_count"] > 0 and glucose_summary["readings_count"] > 0:
            if mood_summary["average"] < 4 and glucose_summary["average"] > 180:
                insights.append("Your mood and glucose levels suggest stress may be affecting both - consider stress management techniques")
            elif mood_summary["average"] > 7 and glucose_summary["average"] < 100:
                insights.append("Great balance! Your positive mood and stable glucose levels indicate good health management")
        
        # Nutrition and glucose correlation
        if nutrition_summary["entries_count"] > 0 and glucose_summary["readings_count"] > 0:
            if nutrition_summary["average_calories"] > 2000 and glucose_summary["average"] > 180:
                insights.append("High calorie intake may be affecting glucose levels - consider portion control")
            elif nutrition_summary["average_carbs"] > 250 and glucose_summary["average"] > 160:
                insights.append("High carbohydrate intake may be impacting glucose - consider carb timing and quality")
        
        # Mood and nutrition correlation
        if mood_summary["entries_count"] > 0 and nutrition_summary["entries_count"] > 0:
            if mood_summary["average"] < 4 and nutrition_summary["average_calories"] < 1200:
                insights.append("Low mood and low calorie intake may be related - consider mood-supporting foods")
            elif mood_summary["average"] > 7 and nutrition_summary["average_protein"] > 80:
                insights.append("Good protein intake may be supporting your positive mood - keep it up!")
        
        return insights

def main():
    """Main function to run the health agent system"""
    print("🏥 Health Agent System Starting...")
    print("="*50)
    
    # Initialize system
    health_system = HealthAgentSystem()
    
    print("""
🎉 **Welcome to your Personal Health Assistant!**

This AI-powered system helps you track and manage your health data:
• Mood tracking with trend analysis
• Glucose monitoring with smart alerts  
• Food logging with nutrition analysis
• Personalized meal planning
• Health insights and correlations

To get started, please provide your User ID or tell me your name.
Type 'quit' to exit.
    """)
    
    while True:
        try:
            # Get user input
            user_input = input(f"\n[{health_system.system_state}] You: ").strip()
            
            # Handle quit
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\n👋 Thank you for using the Health Agent System. Stay healthy!")
                break
            
            # Process input
            result = health_system.process_user_input(user_input)
            
            # Display response
            print(f"\n🤖 Assistant: {result['response']}")
            
            # Show debug info if needed
            if os.getenv("DEBUG") == "true":
                print(f"\n[DEBUG] Agent: {result['agent_used']}, State: {result['system_state']}")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Stay healthy!")
            break
        except Exception as e:
            print(f"\n❌ System Error: {str(e)}")
            print("Please try again or type 'quit' to exit.")

if __name__ == "__main__":
    main()