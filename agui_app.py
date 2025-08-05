# agui_app.py - Pure AG-UI Application for Health Agent System
import os
from dotenv import load_dotenv
from fastapi import Request
from agno.models.google import Gemini

# Load environment variables
load_dotenv()


# Import the main health agent system
from main import HealthAgentSystem

# Import Agno components for AG-UI
from agno.app.agui.app import AGUIApp
from agno.agent.agent import Agent
from agno.models.openai import OpenAIChat

class HealthAgent(Agent):
    """
    Health Assistant Agent using pure AGUI protocols with proper authentication
    """
    def __init__(self):
        super().__init__(
            name="Health Assistant",
            model=Gemini(
            id=os.environ['DEFAULT_MODEL'],
            vertexai=False,
            project_id=os.environ['GOOGLE_CLOUD_PROJECT'],
            location=os.environ['GOOGLE_CLOUD_LOCATION'],
            api_key=os.environ.get('GOOGLE_API_KEY')),
            instructions=[
                "You are a comprehensive health assistant that helps users track and manage their health data.",
                "You can help with mood tracking, glucose monitoring, food logging, meal planning, and health insights.",
                "Always maintain a friendly, supportive, and encouraging tone.",
                "First, users need to authenticate with their user ID or name.",
                "After authentication, you can help them with various health-related tasks.",
                "Provide personalized responses based on their health data and preferences.",
                "When users provide their user ID or name, authenticate them first before proceeding with health tasks.",
                "Remember user context throughout the conversation.",
                "Always respond in a helpful and supportive manner.",
                "Use markdown formatting for better readability.",
                "Greet users with their name and location after successful authentication.",
                "When users want to log data, use the specific logging tools to ensure data is properly stored."
            ],
            description="A multi-agent health tracking and management system",
            show_tool_calls=True,
            markdown=True
        )
        
        # Initialize the health agent system
        self.health_system = HealthAgentSystem()
        
        # Add tools for health system integration
        self.add_tool(self.process_health_request)
        self.add_tool(self.authenticate_user)
        self.add_tool(self.search_user_by_name)
        self.add_tool(self.get_health_dashboard_data)
        self.add_tool(self.get_system_status)
        self.add_tool(self.logout_user)
        self.add_tool(self.reset_system_state)
        
        # Add specific agent tools for direct data logging
        self.add_tool(self.log_mood_direct)
        self.add_tool(self.log_glucose_direct)
        self.add_tool(self.log_food_direct)
        self.add_tool(self.generate_meal_plan_direct)
        self.add_tool(self.get_mood_trends_direct)
        self.add_tool(self.get_glucose_trends_direct)
        self.add_tool(self.get_nutrition_insights_direct)
    
    def process_health_request(self, user_input: str) -> str:
        """
        Process a health-related request from the user
        
        Args:
            user_input: The user's input/request
            
        Returns:
            Response from the health system
        """
        try:
            print(f"Processing health request: {user_input}")
            result = self.health_system.process_user_input(user_input)
            response = result.get("response", "I couldn't process that request.")
            print(f"Health system response: {response}")
            return response
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            print(f"Error in process_health_request: {error_msg}")
            return error_msg
    
    def log_mood_direct(self, mood_description: str) -> str:
        """
        Directly log mood data to ensure proper database storage
        
        Args:
            mood_description: Description of the user's mood
            
        Returns:
            Confirmation message
        """
        if self.health_system.system_state != "authenticated":
            return "❌ Please authenticate first before logging mood data."
        
        try:
            if not self.health_system.mood_tracker_agent:
                self.health_system._initialize_authenticated_agents()
            
            result = self.health_system.mood_tracker_agent.log_mood(mood_description)
            return result.get("message", "Mood logged successfully!")
        except Exception as e:
            return f"Error logging mood: {str(e)}"
    
    def log_glucose_direct(self, glucose_reading: float) -> str:
        """
        Directly log glucose reading to ensure proper database storage
        
        Args:
            glucose_reading: The glucose reading in mg/dL
            
        Returns:
            Confirmation message
        """
        if self.health_system.system_state != "authenticated":
            return "❌ Please authenticate first before logging glucose data."
        
        try:
            if not self.health_system.cgm_agent:
                self.health_system._initialize_authenticated_agents()
            
            result = self.health_system.cgm_agent.process_glucose_reading(glucose_reading)
            return result.get("message", "Glucose reading logged successfully!")
        except Exception as e:
            return f"Error logging glucose: {str(e)}"
    
    def log_food_direct(self, meal_description: str) -> str:
        """
        Directly log food intake to ensure proper database storage
        
        Args:
            meal_description: Description of the meal consumed
            
        Returns:
            Confirmation message
        """
        if self.health_system.system_state != "authenticated":
            return "❌ Please authenticate first before logging food data."
        
        try:
            if not self.health_system.food_intake_agent:
                self.health_system._initialize_authenticated_agents()
            
            result = self.health_system.food_intake_agent.log_meal(meal_description)
            return result.get("message", "Food logged successfully!")
        except Exception as e:
            return f"Error logging food: {str(e)}"
    
    def generate_meal_plan_direct(self, plan_date: str = None) -> str:
        """
        Directly generate meal plan to ensure proper database storage
        
        Args:
            plan_date: Date for the meal plan (optional)
            
        Returns:
            Meal plan response
        """
        if self.health_system.system_state != "authenticated":
            return "❌ Please authenticate first before generating meal plans."
        
        try:
            if not self.health_system.meal_planner_agent:
                self.health_system._initialize_authenticated_agents()
            
            result = self.health_system.meal_planner_agent.generate_meal_plan(plan_date)
            return result.get("message", "Meal plan generated successfully!")
        except Exception as e:
            return f"Error generating meal plan: {str(e)}"
    
    def get_mood_trends_direct(self) -> str:
        """
        Get mood trends directly from the database
        
        Returns:
            Mood trends summary
        """
        if self.health_system.system_state != "authenticated":
            return "❌ Please authenticate first to view mood trends."
        
        try:
            if not self.health_system.mood_tracker_agent:
                self.health_system._initialize_authenticated_agents()
            
            result = self.health_system.mood_tracker_agent.get_mood_trends()
            if result.get("entries_count", 0) > 0:
                return f"📊 **Mood Trends:**\n\nAverage: {result['average_mood']}/10\nEntries: {result['entries_count']}\nTrend: {result['trend']}"
            else:
                return "No mood data available. Start logging your mood!"
        except Exception as e:
            return f"Error getting mood trends: {str(e)}"
    
    def get_glucose_trends_direct(self) -> str:
        """
        Get glucose trends directly from the database
        
        Returns:
            Glucose trends summary
        """
        if self.health_system.system_state != "authenticated":
            return "❌ Please authenticate first to view glucose trends."
        
        try:
            if not self.health_system.cgm_agent:
                self.health_system._initialize_authenticated_agents()
            
            result = self.health_system.cgm_agent.get_glucose_trends()
            if result.get("readings_count", 0) > 0:
                return f"📈 **Glucose Trends:**\n\nAverage: {result['average_glucose']} mg/dL\nReadings: {result['readings_count']}\nTrend: {result['trend']}"
            else:
                return "No glucose data available. Start logging your readings!"
        except Exception as e:
            return f"Error getting glucose trends: {str(e)}"
    
    def get_nutrition_insights_direct(self) -> str:
        """
        Get nutrition insights directly from the database
        
        Returns:
            Nutrition insights summary
        """
        if self.health_system.system_state != "authenticated":
            return "❌ Please authenticate first to view nutrition insights."
        
        try:
            if not self.health_system.food_intake_agent:
                self.health_system._initialize_authenticated_agents()
            
            result = self.health_system.food_intake_agent.get_nutrition_insights()
            if result.get("days_analyzed", 0) > 0:
                averages = result['averages']
                return f"🥗 **Nutrition Insights:**\n\nCalories: {averages['calories']} kcal/day\nProtein: {averages['protein']}g\nCarbs: {averages['carbs']}g\nFat: {averages['fat']}g"
            else:
                return "No nutrition data available. Start logging your meals!"
        except Exception as e:
            return f"Error getting nutrition insights: {str(e)}"
    
    def authenticate_user(self, user_id: str) -> str:
        """
        Authenticate a user with their user ID
        
        Args:
            user_id: The user ID to authenticate
            
        Returns:
            Authentication result message
        """
        try:
            print(f"Authenticating user: {user_id}")
            
            # Reset the health system state to ensure clean authentication
            self.health_system.authenticated_user_id = None
            self.health_system.current_user_name = None
            self.health_system.system_state = "unauthenticated"
            
            # Clear authenticated agents to force re-initialization
            self.health_system.cgm_agent = None
            self.health_system.mood_tracker_agent = None
            self.health_system.food_intake_agent = None
            self.health_system.meal_planner_agent = None
            
            result = self.health_system.process_user_input(user_id.strip())
            response = result.get("response", "Authentication failed.")
            print(f"Authentication result: {response}")
            return response
        except Exception as e:
            error_msg = f"Authentication error: {str(e)}"
            print(f"Authentication error: {error_msg}")
            return error_msg
    
    def search_user_by_name(self, name: str) -> str:
        """
        Search for a user by name
        
        Args:
            name: The name to search for
            
        Returns:
            Search result message
        """
        try:
            print(f"Searching for user: {name}")
            
            # Reset the health system state to ensure clean search
            self.health_system.authenticated_user_id = None
            self.health_system.current_user_name = None
            self.health_system.system_state = "unauthenticated"
            
            # Clear authenticated agents to force re-initialization
            self.health_system.cgm_agent = None
            self.health_system.mood_tracker_agent = None
            self.health_system.food_intake_agent = None
            self.health_system.meal_planner_agent = None
            
            # Format the search input like in main.py
            search_input = f"My name is {name}"
            result = self.health_system.process_user_input(search_input)
            response = result.get("response", "Search failed.")
            print(f"Search result: {response}")
            return response
        except Exception as e:
            error_msg = f"Search error: {str(e)}"
            print(f"Search error: {error_msg}")
            return error_msg
    
    def get_health_dashboard_data(self) -> str:
        """
        Get dashboard data for the authenticated user
        
        Returns:
            Formatted dashboard data
        """
        if self.health_system.system_state != "authenticated":
            return "❌ Please authenticate with your user ID first."
        
        try:
            # Use the enhanced database method for comprehensive dashboard
            from utils.database import DatabaseManager
            db = DatabaseManager()
            health_summary = db.get_health_summary(self.health_system.authenticated_user_id)
            
            if not health_summary:
                return "📊 **Health Dashboard**\n\nNo health data available yet. Start by logging your mood, glucose readings, or food intake!"
            
            user_info = health_summary["user_info"]
            mood_summary = health_summary["mood_summary"]
            glucose_summary = health_summary["glucose_summary"]
            nutrition_summary = health_summary["nutrition_summary"]
            
            dashboard_info = []
            
            if mood_summary["entries_count"] > 0:
                dashboard_info.append(f"😊 **Mood**: {mood_summary['average']}/10 average ({mood_summary['entries_count']} entries)")
            
            if glucose_summary["readings_count"] > 0:
                dashboard_info.append(f"🩸 **Glucose**: {glucose_summary['average']} mg/dL average ({glucose_summary['readings_count']} readings)")
            
            if nutrition_summary["entries_count"] > 0:
                dashboard_info.append(f"🍽️ **Nutrition**: {nutrition_summary['average_calories']:.0f} kcal/day average ({nutrition_summary['entries_count']} meals)")
            
            if dashboard_info:
                return f"📊 **Health Dashboard for {user_info['name']}**\n\n" + "\n".join(dashboard_info)
            else:
                return "📊 **Health Dashboard**\n\nNo health data available yet. Start by logging your mood, glucose readings, or food intake!"
                
        except Exception as e:
            return f"Failed to retrieve dashboard data: {str(e)}"
    
    def get_system_status(self) -> str:
        """
        Get the current system status
        
        Returns:
            System status information
        """
        status = self.health_system.system_state
        user_name = self.health_system.current_user_name
        
        if status == "authenticated" and user_name:
            return f"✅ **Status**: Authenticated as {user_name}\n🔧 **Available**: Mood tracking, glucose monitoring, food logging, meal planning"
        else:
            return "🔐 **Status**: Not authenticated\n💡 **To get started**: Please provide your user ID or say 'My name is [Your Name]'"
    
    def logout_user(self) -> str:
        """
        Logout the current user
        
        Returns:
            Logout confirmation message
        """
        try:
            result = self.health_system.process_user_input("logout")
            response = result.get("response", "Logout failed.")
            return response
        except Exception as e:
            error_msg = f"Logout error: {str(e)}"
            print(f"Logout error: {error_msg}")
            return error_msg
    
    def reset_system_state(self) -> str:
        """
        Reset the system state completely
        
        Returns:
            Reset confirmation message
        """
        try:
            # Reset the health system state completely
            self.health_system.authenticated_user_id = None
            self.health_system.current_user_name = None
            self.health_system.system_state = "unauthenticated"
            
            # Clear authenticated agents
            self.health_system.cgm_agent = None
            self.health_system.mood_tracker_agent = None
            self.health_system.food_intake_agent = None
            self.health_system.meal_planner_agent = None
            
            return "🔄 **System State Reset**\n\nAll user data has been cleared. Please authenticate with your user ID or name to continue."
        except Exception as e:
            error_msg = f"Reset error: {str(e)}"
            print(f"Reset error: {error_msg}")
            return error_msg

# Setup your Agno Health Agent
health_agent = HealthAgent()

# Setup the AG-UI app
agui_app = AGUIApp(
    agent=health_agent,
    name="Health Assistant",
    app_id="health_agent",
)

# Get the app for external use (like CopilotKit integration)
app = agui_app.get_app()

# Add CORS middleware for frontend integration
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://frontend:3000",
        "http://health-frontend:3000",
        "*"  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "health-agent-backend"}

# The AG-UI integration handles all chat requests automatically
# No need for a separate /chat endpoint

# Authentication is now properly handled through the AG-UI agent integration
# Users can authenticate by saying "My name is [Name]" or providing their user ID
# The agent will handle authentication automatically and greet users with their name and location

if __name__ == "__main__":
    # Serve the app, effectively exposing your Agno Health Agent
    agui_app.serve(
        app="agui_app:app",
        port=8000,
        host="0.0.0.0",  # Listen on all interfaces
        reload=True
    )