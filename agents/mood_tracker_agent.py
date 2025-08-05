# agents/mood_tracker_agent.py
from agno.agent import Agent
from agno.models.google import Gemini
from typing import Dict, Any, List
import sys
from dotenv import load_dotenv
import os

load_dotenv()
from datetime import datetime, timedelta

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from utils.database import DatabaseManager

class MoodTrackerAgent(Agent):
    def __init__(self, authenticated_user_id: str = None):
        super().__init__(
            name="MoodTrackerAgent",
            model=Gemini(
            id=os.environ['DEFAULT_MODEL'],
            vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI'],
            project_id=os.environ['GOOGLE_CLOUD_PROJECT'],
            location=os.environ['GOOGLE_CLOUD_LOCATION'],
            api_key=os.environ.get('GOOGLE_API_KEY')),
            description="Tracks user mood and computes mood patterns and insights",
            instructions=[
                "You are a caring mood tracking specialist.",
                "Help users log their daily moods and provide insights on patterns.",
                "Convert mood labels to numerical scores for analysis.",
                "Provide supportive feedback and suggestions for mood improvement.",
                "Track correlations between mood and other health metrics.",
                "Be empathetic and encouraging in all interactions."
            ],
            show_tool_calls=True,
            markdown=True
        )
        self.db = DatabaseManager()
        self.authenticated_user_id = authenticated_user_id
        
        # Mood scoring system (mapped to simplified labels)
        self.mood_scores = {
            "terrible": 1, "awful": 1, "horrible": 1,
            "depressed": 2, "miserable": 2,
            "sad": 3, "down": 3, "low": 3,
            "tired": 4, "bad": 4,
            "okay": 5, "neutral": 5, "fine": 5,
            "good": 6, "decent": 6, "alright": 6,
            "happy": 7, "positive": 7, "cheerful": 7,
            "great": 8, "wonderful": 8, "fantastic": 8,
            "excited": 9, "amazing": 9, "thrilled": 9,
            "ecstatic": 10, "overjoyed": 10, "blissful": 10
        }
        
        # Add custom tools
        self.add_tool(self.log_mood)
        self.add_tool(self.get_mood_trends)
        self.add_tool(self.get_mood_insights)
        self.add_tool(self.suggest_mood_boosters)
        self.add_tool(self.convert_mood_to_score)
        self.add_tool(self.extract_simple_mood_label)
    
    def set_authenticated_user(self, user_id: str):
        """Set the authenticated user for this session"""
        self.authenticated_user_id = user_id
    
    def extract_simple_mood_label(self, mood_input: str) -> str:
        """
        Extract a simple mood label from user input
        
        Args:
            mood_input: The raw mood input from user
            
        Returns:
            Simple mood label (e.g., "great", "good", "bad", "awesome", etc.)
        """
        mood_lower = mood_input.lower().strip()
        
        # Check for negative moods first (more specific to less specific)
        if any(word in mood_lower for word in ['terrible', 'awful', 'horrible', 'worst']):
            return "terrible"
        elif any(word in mood_lower for word in ['very sad', 'depressed', 'miserable', 'devastated']):
            return "depressed"
        elif any(word in mood_lower for word in ['sad', 'down', 'low', 'blue', 'upset']):
            return "sad"
        elif any(word in mood_lower for word in ['tired', 'sluggish', 'drained', 'exhausted', 'weary']):
            return "tired"
        elif any(word in mood_lower for word in ['bad', 'not good', 'poor', 'rough']):
            return "bad"
        
        # Check for positive moods (more specific to less specific)
        elif any(word in mood_lower for word in ['ecstatic', 'overjoyed', 'blissful', 'euphoric', 'elated']):
            return "ecstatic"
        elif any(word in mood_lower for word in ['excited', 'amazing', 'thrilled', 'energetic', 'pumped']):
            return "excited"
        elif any(word in mood_lower for word in ['great', 'wonderful', 'fantastic', 'awesome', 'excellent']):
            return "great"
        elif any(word in mood_lower for word in ['happy', 'positive', 'cheerful', 'content', 'joyful']):
            return "happy"
        elif any(word in mood_lower for word in ['good', 'decent', 'alright', 'better', 'well']):
            return "good"
        
        # Default cases
        elif any(word in mood_lower for word in ['okay', 'fine', 'meh', 'so-so']):
            return "okay"
        else:
            # If no clear match, try to infer from overall tone
            positive_words = ['love', 'like', 'enjoy', 'nice', 'pleasant', 'bright']
            negative_words = ['hate', 'dislike', 'stress', 'worry', 'angry', 'frustrated']
            
            pos_count = sum(1 for word in positive_words if word in mood_lower)
            neg_count = sum(1 for word in negative_words if word in mood_lower)
            
            if pos_count > neg_count:
                return "good"
            elif neg_count > pos_count:
                return "down"
            else:
                return "neutral"

    def convert_mood_to_score(self, mood_label: str) -> Dict[str, Any]:
        """
        Convert mood label to numerical score
        
        Args:
            mood_label: The mood label/description
            
        Returns:
            Dict containing the mood score and interpretation
        """
        mood_lower = mood_label.lower().strip()
        
        # Direct match
        if mood_lower in self.mood_scores:
            score = self.mood_scores[mood_lower]
        else:
            # Fuzzy matching for common variations
            score = 5  # Default neutral
            
            # Negative moods
            if any(word in mood_lower for word in ['terrible', 'awful', 'horrible', 'worst']):
                score = 1
            elif any(word in mood_lower for word in ['very sad', 'depressed', 'miserable', 'devastated']):
                score = 2
            elif any(word in mood_lower for word in ['sad', 'down', 'low', 'blue', 'upset']):
                score = 3
            elif any(word in mood_lower for word in ['tired', 'sluggish', 'drained', 'exhausted', 'weary']):
                score = 4
            # Positive moods
            elif any(word in mood_lower for word in ['good', 'decent', 'alright', 'better']):
                score = 6
            elif any(word in mood_lower for word in ['happy', 'positive', 'cheerful', 'content']):
                score = 7
            elif any(word in mood_lower for word in ['great', 'wonderful', 'fantastic', 'awesome']):
                score = 8
            elif any(word in mood_lower for word in ['excited', 'amazing', 'thrilled', 'energetic']):
                score = 9
            elif any(word in mood_lower for word in ['ecstatic', 'overjoyed', 'blissful', 'euphoric']):
                score = 10
        
        # Interpret score
        if score <= 2:
            interpretation = "Very Low - Consider reaching out for support"
        elif score <= 4:
            interpretation = "Low - Self-care and rest may help"
        elif score == 5:
            interpretation = "Neutral - A typical day"
        elif score <= 7:
            interpretation = "Good - Positive and stable"
        elif score <= 9:
            interpretation = "High - Feeling great!"
        else:
            interpretation = "Very High - Excellent mood!"
        
        return {
            "mood_label": mood_label,
            "mood_score": score,
            "interpretation": interpretation
        }
    
    def log_mood(self, mood_input: str) -> Dict[str, Any]:
        """
        Log a mood entry for the authenticated user
        
        Args:
            mood_input: The raw mood description from user
            
        Returns:
            Dict containing confirmation and mood insights
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first before logging your mood."
            }
        
        # Extract simple mood label from user input
        simple_mood_label = self.extract_simple_mood_label(mood_input)
        
        # Convert mood to score
        mood_data = self.convert_mood_to_score(simple_mood_label)
        score = mood_data["mood_score"]
        
        # Store simplified mood label in database (not the full input)
        self.db.store_mood(self.authenticated_user_id, simple_mood_label, score)
        
        # Log the interaction for tracking
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "MoodTrackerAgent",
            "Database",
            "mood_logging",
            f"Mood: {simple_mood_label} (Score: {score}/10)"
        )
        
        # Get rolling average
        rolling_avg = self.db.get_mood_rolling_average(self.authenticated_user_id, 7)
        
        # Generate response message
        message = f"Mood logged: **{simple_mood_label}** (Score: {score}/10)"
        if mood_input.lower().strip() != simple_mood_label.lower():
            message += f"\nFrom: \"{mood_input}\""
        
        if rolling_avg > 0:
            message += f"\nYour 7-day average: {rolling_avg}/10"
            
            if score > rolling_avg + 1:
                message += "\nThat's higher than your recent average - great to see!"
            elif score < rolling_avg - 1:
                message += "\nThat's lower than usual - remember to be kind to yourself."
        
        # Add mood-based recommendations
        recommendations = self._get_mood_based_recommendations(score, rolling_avg)
        if recommendations:
            message += f"\n\n💡 **Suggestions:** {recommendations}"
        
        return {
            "status": "success",
            "message": message,
            "mood_score": score,
            "interpretation": mood_data["interpretation"],
            "rolling_average": rolling_avg,
            "recommendations": recommendations
        }
    
    def _get_mood_based_recommendations(self, current_score: int, rolling_avg: float) -> str:
        """Get personalized recommendations based on mood"""
        if current_score <= 3:
            if rolling_avg > 0 and current_score < rolling_avg - 2:
                return "Consider reaching out to a friend or family member. Your mood has been lower than usual."
            else:
                return "Try some gentle self-care activities like deep breathing or a warm bath."
        elif current_score <= 5:
            if rolling_avg > 0 and current_score < rolling_avg - 1:
                return "A short walk or listening to your favorite music might help lift your spirits."
            else:
                return "Consider activities that bring you joy, even small ones."
        elif current_score >= 8:
            return "Great energy! Consider channeling this positive mood into productive activities."
        else:
            return "You're doing well! Keep up the positive momentum."
    
    def get_mood_trends(self, days: int = 30) -> Dict[str, Any]:
        """
        Get mood trends and patterns over time
        
        Args:
            days: Number of days to analyze (default 30)
            
        Returns:
            Dict containing mood trend analysis
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to view mood trends."
            }
        
        # Use the enhanced database method
        mood_data = self.db.get_recent_mood_data(self.authenticated_user_id, days)
        
        if mood_data["entries_count"] == 0:
            return {
                "status": "success",
                "message": f"No mood entries found in the past {days} days.",
                "entries_count": 0
            }
        
        # Log the interaction for tracking
        self.db.log_agent_interaction(
            self.authenticated_user_id,
            "MoodTrackerAgent",
            "User",
            "trend_analysis",
            f"Analyzed {mood_data['entries_count']} mood entries over {days} days"
        )
        
        return {
            "status": "success",
            "entries_count": mood_data["entries_count"],
            "average_mood": mood_data["average_mood"],
            "trend": mood_data["trend"],
            "recent_entries": mood_data["recent_entries"]
        }
    
    def get_mood_insights(self) -> Dict[str, Any]:
        """
        Get personalized mood insights and correlations
        
        Returns:
            Dict containing mood insights and recommendations
        """
        if not self.authenticated_user_id:
            return {
                "status": "error",
                "message": "Please log in first to get mood insights."
            }
        
        trends = self.get_mood_trends(30)
        if trends["entries_count"] == 0:
            return {
                "status": "success",
                "message": "Not enough mood data for insights. Keep logging your mood daily!"
            }
        
        insights = []
        recommendations = []
        
        avg_mood = trends["average_mood"]
        
        # General insights based on average
        if avg_mood >= 7:
            insights.append("You've been maintaining a positive mood - excellent!")
            recommendations.append("Keep doing what you're doing!")
        elif avg_mood >= 5:
            insights.append("Your mood has been generally balanced.")
            recommendations.append("Consider activities that bring you joy to boost your mood further.")
        else:
            insights.append("Your mood has been lower than ideal recently.")
            recommendations.append("Consider speaking with a counselor or trusted friend.")
            recommendations.append("Try incorporating mood-boosting activities into your routine.")
        
        # Trend insights
        if trends["trend"] == "improving":
            insights.append("Great news! Your mood trend is improving over time.")
        elif trends["trend"] == "declining":
            insights.append("Your mood trend shows some decline - let's work on reversing this.")
            recommendations.append("Identify any recent stressors or changes in routine.")
        
        # Consistency insights
        mood_range = trends["max_mood"] - trends["min_mood"]
        if mood_range <= 3:
            insights.append("Your mood has been quite stable - that's a positive sign.")
        elif mood_range >= 6:
            insights.append("You've experienced significant mood swings recently.")
            recommendations.append("Try to identify triggers for mood changes.")
        
        return {
            "status": "success",
            "insights": insights,
            "recommendations": recommendations,
            "overall_assessment": self._get_overall_assessment(avg_mood, trends["trend"])
        }
    
    def suggest_mood_boosters(self, current_mood_score: int = None) -> Dict[str, Any]:
        """
        Suggest activities to improve mood based on current state
        
        Args:
            current_mood_score: Current mood score (1-10)
            
        Returns:
            Dict containing personalized mood-boosting suggestions
        """
        if not current_mood_score:
            # Get recent mood if not provided
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT mood_score FROM mood_tracking 
                       WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1""",
                    (self.authenticated_user_id,)
                )
                result = cursor.fetchone()
                current_mood_score = result[0] if result else 5
        
        suggestions = []
        
        if current_mood_score <= 3:
            # Low mood - gentle, nurturing activities
            suggestions = [
                "Take a warm bath or shower to relax",
                "Listen to calming music or nature sounds",
                "Practice deep breathing for 5-10 minutes",
                "Reach out to a supportive friend or family member",
                "Write in a journal about your feelings",
                "Watch a comforting movie or TV show",
                "Get some sunlight, even if just by a window"
            ]
        elif current_mood_score <= 5:
            # Neutral to low - activating but not overwhelming
            suggestions = [
                "Go for a short walk, preferably outdoors",
                "Do some light stretching or yoga",
                "Listen to your favorite upbeat music",
                "Complete a small, achievable task",
                "Call or text someone you care about",
                "Practice gratitude - list 3 things you're thankful for",
                "Prepare a healthy, colorful meal"
            ]
        elif current_mood_score <= 7:
            # Good mood - maintain and build
            suggestions = [
                "Exercise or dance to your favorite music",
                "Try a new hobby or creative activity",
                "Spend time with friends or loved ones",
                "Plan something fun for the near future",
                "Help someone else or do a kind deed",
                "Explore somewhere new in your area",
                "Practice a skill you want to improve"
            ]
        else:
            # High mood - channel the energy positively
            suggestions = [
                "Share your positive energy with others",
                "Start a project you've been putting off",
                "Exercise or do physical activities you enjoy",
                "Document this good feeling in a journal",
                "Plan future activities that make you happy",
                "Express creativity through art, music, or writing",
                "Celebrate your accomplishments, big or small"
            ]
        
        return {
            "status": "success",
            "current_mood_score": current_mood_score,
            "suggestions": suggestions[:5],  # Top 5 suggestions
            "message": f"Here are some mood-boosting activities tailored for your current mood level ({current_mood_score}/10):"
        }
    
    def _get_overall_assessment(self, avg_mood: float, trend: str) -> str:
        """Generate overall mood assessment"""
        if avg_mood >= 7 and trend in ["improving", "stable"]:
            return "Excellent - You're maintaining great mental wellness!"
        elif avg_mood >= 5 and trend == "improving":
            return "Good - You're on a positive trajectory!"
        elif avg_mood >= 5 and trend == "stable":
            return "Stable - You're managing well overall."
        elif trend == "improving":
            return "Encouraging - Your mood is trending upward!"
        else:
            return "Needs attention - Consider focusing on mood-supporting activities."

# Convenience function to create the agent
def create_mood_tracker_agent(authenticated_user_id: str = None):
    return MoodTrackerAgent(authenticated_user_id)