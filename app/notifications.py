"""
Notification Service

Handles email notifications, alerts, and communication with users.
"""

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import ssl
import logging
from jinja2 import Template

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending notifications via email and other channels.

    Handles various types of notifications: welcome emails, trade alerts,
    challenge status updates, payment confirmations, risk warnings, etc.
    """

    def __init__(self):
        # Email configuration
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME', 'noreply@tradesense.ai')
        self.smtp_password = os.getenv('SMTP_PASSWORD', 'your_password_here')

        # Email templates
        self.templates = self._load_templates()

        # Notification preferences (in production, this would come from user preferences)
        self.default_preferences = {
            'welcome_email': True,
            'challenge_updates': True,
            'trade_alerts': False,  # Disabled by default to avoid spam
            'payment_confirmations': True,
            'risk_warnings': True,
            'weekly_summary': True,
            'achievement_unlocked': True,
            'leaderboard_updates': False
        }

    def _load_templates(self) -> Dict[str, Template]:
        """Load email templates."""
        templates = {}

        # Welcome email template
        templates['welcome'] = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Welcome to TradeSense AI</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }
                .content { padding: 30px; max-width: 600px; margin: 0 auto; }
                .button { display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
                .footer { background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎯 Welcome to TradeSense AI!</h1>
                <p>Your AI-powered prop trading platform</p>
            </div>
            <div class="content">
                <h2>Hello {{ user_name }}!</h2>
                <p>Thank you for joining TradeSense AI. You're now part of an exclusive community of traders using cutting-edge AI technology to master prop trading challenges.</p>

                <h3>🚀 What's Next?</h3>
                <ul>
                    <li><strong>Complete your profile</strong> to unlock advanced features</li>
                    <li><strong>Start your first challenge</strong> to begin trading</li>
                    <li><strong>Explore the leaderboard</strong> to see how you rank</li>
                    <li><strong>Connect with other traders</strong> in our community</li>
                </ul>

                <a href="{{ dashboard_url }}" class="button">Start Trading Now</a>

                <p>Need help? Our support team is here for you 24/7.</p>

                <p>Happy trading!<br>The TradeSense AI Team</p>
            </div>
            <div class="footer">
                <p>This email was sent to {{ user_email }}. If you no longer wish to receive these emails, you can <a href="{{ unsubscribe_url }}">unsubscribe</a>.</p>
                <p>&copy; 2024 TradeSense AI. All rights reserved.</p>
            </div>
        </body>
        </html>
        """)

        # Challenge funded notification
        templates['challenge_funded'] = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>🎉 Challenge Funded!</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .header { background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); color: white; padding: 30px; text-align: center; }
                .content { padding: 30px; max-width: 600px; margin: 0 auto; }
                .stats { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
                .stat { display: inline-block; margin: 0 20px 10px 0; }
                .button { display: inline-block; padding: 12px 24px; background: #4CAF50; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎉 Congratulations! Challenge Funded!</h1>
            </div>
            <div class="content">
                <h2>Amazing work, {{ user_name }}!</h2>
                <p>You've successfully completed your trading challenge and earned <strong>${{ payout_amount }}</strong>!</p>

                <div class="stats">
                    <div class="stat"><strong>Challenge:</strong> {{ challenge_type }}</div>
                    <div class="stat"><strong>Final Equity:</strong> ${{ final_equity }}</div>
                    <div class="stat"><strong>Total Return:</strong> {{ total_return }}%</div>
                    <div class="stat"><strong>Duration:</strong> {{ duration_days }} days</div>
                </div>

                <p>Your payout will be processed within 24-48 hours. You'll receive a separate email when it's available for withdrawal.</p>

                <a href="{{ dashboard_url }}" class="button">View Your Results</a>

                <p>Ready for the next challenge?<br>The TradeSense AI Team</p>
            </div>
        </body>
        </html>
        """)

        # Risk warning notification
        templates['risk_warning'] = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>⚠️ Risk Warning</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .header { background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%); color: white; padding: 30px; text-align: center; }
                .content { padding: 30px; max-width: 600px; margin: 0 auto; }
                .warning { background: #FFF3E0; border-left: 4px solid #FF9800; padding: 20px; margin: 20px 0; }
                .button { display: inline-block; padding: 12px 24px; background: #FF9800; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>⚠️ Risk Warning</h1>
            </div>
            <div class="content">
                <h2>{{ user_name }}, please review your trading activity</h2>

                <div class="warning">
                    <p><strong>Risk Level:</strong> {{ risk_level }}</p>
                    <p><strong>Risk Score:</strong> {{ risk_score }}/100</p>
                    <p><strong>Issues Detected:</strong></p>
                    <ul>
                        {% for issue in risk_issues %}
                        <li>{{ issue }}</li>
                        {% endfor %}
                    </ul>
                </div>

                <p>Our AI risk monitoring system has detected potentially risky trading behavior. Please review your strategy and consider taking a break if needed.</p>

                <p><strong>Recommendations:</strong></p>
                <ul>
                    <li>Take a break from trading</li>
                    <li>Review your risk management rules</li>
                    <li>Consider paper trading first</li>
                    <li>Contact support if you need help</li>
                </ul>

                <a href="{{ dashboard_url }}" class="button">Review Your Account</a>

                <p>Stay safe and trade responsibly.<br>The TradeSense AI Team</p>
            </div>
        </body>
        </html>
        """)

        # Weekly summary
        templates['weekly_summary'] = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>📊 Your Weekly Trading Summary</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .header { background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%); color: white; padding: 30px; text-align: center; }
                .content { padding: 30px; max-width: 600px; margin: 0 auto; }
                .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }
                .stat-card { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }
                .positive { color: #4CAF50; }
                .negative { color: #f44336; }
                .button { display: inline-block; padding: 12px 24px; background: #2196F3; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Your Weekly Trading Summary</h1>
                <p>{{ week_period }}</p>
            </div>
            <div class="content">
                <h2>Hello {{ user_name }}!</h2>
                <p>Here's your trading performance for the past week:</p>

                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>Challenges</h3>
                        <p class="positive">{{ weekly_challenges }} completed</p>
                    </div>
                    <div class="stat-card">
                        <h3>Total P&L</h3>
                        <p class="{{ 'positive' if weekly_pnl >= 0 else 'negative' }}">${{ weekly_pnl }}</p>
                    </div>
                    <div class="stat-card">
                        <h3>Win Rate</h3>
                        <p>{{ weekly_win_rate }}%</p>
                    </div>
                    <div class="stat-card">
                        <h3>Best Trade</h3>
                        <p class="positive">${{ best_trade }}</p>
                    </div>
                </div>

                <h3>🏆 Achievements This Week</h3>
                <ul>
                    {% for achievement in weekly_achievements %}
                    <li>{{ achievement }}</li>
                    {% endfor %}
                </ul>

                <h3>📈 Your Ranking</h3>
                <p>You're currently ranked #{{ current_rank }} in the global leaderboard.</p>

                <a href="{{ dashboard_url }}" class="button">View Full Details</a>

                <p>Keep up the great work!<br>The TradeSense AI Team</p>
            </div>
        </body>
        </html>
        """)

        return templates

    def send_email(self, to_email: str, subject: str, html_content: str, from_name: str = "TradeSense AI") -> bool:
        """
        Send an email using SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email content
            from_name: Sender name

        Returns:
            Success status
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{from_name} <{self.smtp_username}>"
            msg['To'] = to_email

            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            # Create secure SSL context
            context = ssl.create_default_context()

            # Connect to SMTP server and send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(self.smtp_username, to_email, msg.as_string())

            logger.info(f"Email sent successfully to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_welcome_email(self, user_email: str, user_name: str) -> bool:
        """Send welcome email to new users."""
        try:
            template = self.templates['welcome']
            html_content = template.render(
                user_name=user_name,
                user_email=user_email,
                dashboard_url="https://tradesense.ai/dashboard",
                unsubscribe_url="https://tradesense.ai/unsubscribe"
            )

            return self.send_email(
                to_email=user_email,
                subject="🎯 Welcome to TradeSense AI - Your Trading Journey Begins!",
                html_content=html_content
            )
        except Exception as e:
            logger.error(f"Failed to send welcome email to {user_email}: {e}")
            return False

    def send_challenge_funded_email(self, user_email: str, user_name: str, challenge_data: Dict) -> bool:
        """Send challenge funded notification."""
        try:
            template = self.templates['challenge_funded']
            html_content = template.render(
                user_name=user_name,
                payout_amount=challenge_data.get('payout_amount', 0),
                challenge_type=challenge_data.get('challenge_type', 'Unknown'),
                final_equity=challenge_data.get('final_equity', 0),
                total_return=challenge_data.get('total_return', 0),
                duration_days=challenge_data.get('duration_days', 0),
                dashboard_url="https://tradesense.ai/dashboard"
            )

            return self.send_email(
                to_email=user_email,
                subject=f"🎉 Congratulations! Your ${challenge_data.get('payout_amount', 0)} Payout is Ready",
                html_content=html_content
            )
        except Exception as e:
            logger.error(f"Failed to send challenge funded email to {user_email}: {e}")
            return False

    def send_risk_warning_email(self, user_email: str, user_name: str, risk_data: Dict) -> bool:
        """Send risk warning notification."""
        try:
            template = self.templates['risk_warning']
            html_content = template.render(
                user_name=user_name,
                risk_level=risk_data.get('risk_level', 'Unknown'),
                risk_score=risk_data.get('risk_score', 0),
                risk_issues=risk_data.get('issues', []),
                dashboard_url="https://tradesense.ai/dashboard"
            )

            return self.send_email(
                to_email=user_email,
                subject=f"⚠️ Risk Warning - {risk_data.get('risk_level', 'Unknown')} Level Detected",
                html_content=html_content
            )
        except Exception as e:
            logger.error(f"Failed to send risk warning email to {user_email}: {e}")
            return False

    def send_weekly_summary_email(self, user_email: str, user_name: str, summary_data: Dict) -> bool:
        """Send weekly trading summary."""
        try:
            template = self.templates['weekly_summary']
            html_content = template.render(
                user_name=user_name,
                week_period=summary_data.get('week_period', 'This Week'),
                weekly_challenges=summary_data.get('weekly_challenges', 0),
                weekly_pnl=summary_data.get('weekly_pnl', 0),
                weekly_win_rate=summary_data.get('weekly_win_rate', 0),
                best_trade=summary_data.get('best_trade', 0),
                weekly_achievements=summary_data.get('achievements', []),
                current_rank=summary_data.get('current_rank', 'N/A'),
                dashboard_url="https://tradesense.ai/dashboard"
            )

            return self.send_email(
                to_email=user_email,
                subject="📊 Your Weekly Trading Summary - TradeSense AI",
                html_content=html_content
            )
        except Exception as e:
            logger.error(f"Failed to send weekly summary email to {user_email}: {e}")
            return False

    def send_payment_confirmation_email(self, user_email: str, user_name: str, payment_data: Dict) -> bool:
        """Send payment confirmation."""
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>💳 Payment Confirmation</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .header {{ background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); color: white; padding: 30px; text-align: center; }}
                    .content {{ padding: 30px; max-width: 600px; margin: 0 auto; }}
                    .receipt {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>💳 Payment Confirmed!</h1>
                </div>
                <div class="content">
                    <h2>Hello {user_name}!</h2>
                    <p>Your payment has been successfully processed.</p>

                    <div class="receipt">
                        <h3>Payment Details</h3>
                        <p><strong>Amount:</strong> ${payment_data.get('amount', 0)}</p>
                        <p><strong>Challenge Type:</strong> {payment_data.get('challenge_type', 'Unknown')}</p>
                        <p><strong>Transaction ID:</strong> {payment_data.get('transaction_id', 'N/A')}</p>
                        <p><strong>Date:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
                    </div>

                    <p>Your challenge is now active! Start trading to work towards funding.</p>

                    <p>Happy trading!<br>The TradeSense AI Team</p>
                </div>
            </body>
            </html>
            """

            return self.send_email(
                to_email=user_email,
                subject="💳 Payment Confirmed - Challenge Activated!",
                html_content=html_content
            )
        except Exception as e:
            logger.error(f"Failed to send payment confirmation email to {user_email}: {e}")
            return False

    def send_achievement_unlocked_email(self, user_email: str, user_name: str, achievement_data: Dict) -> bool:
        """Send achievement unlocked notification."""
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>🏆 Achievement Unlocked!</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .header {{ background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); color: white; padding: 30px; text-align: center; }}
                    .content {{ padding: 30px; max-width: 600px; margin: 0 auto; }}
                    .achievement {{ background: #FFF8DC; border: 2px solid #FFD700; padding: 30px; border-radius: 12px; text-align: center; margin: 20px 0; }}
                    .icon {{ font-size: 48px; margin-bottom: 10px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🏆 Achievement Unlocked!</h1>
                </div>
                <div class="content">
                    <h2>Congratulations, {user_name}!</h2>

                    <div class="achievement">
                        <div class="icon">{achievement_data.get('icon', '🏆')}</div>
                        <h3>{achievement_data.get('name', 'New Achievement')}</h3>
                        <p>{achievement_data.get('description', '')}</p>
                    </div>

                    <p>Keep up the great work and unlock more achievements!</p>

                    <p>The TradeSense AI Team</p>
                </div>
            </body>
            </html>
            """

            return self.send_email(
                to_email=user_email,
                subject=f"🏆 New Achievement: {achievement_data.get('name', 'Unknown')}",
                html_content=html_content
            )
        except Exception as e:
            logger.error(f"Failed to send achievement email to {user_email}: {e}")
            return False

    def queue_notification(self, user_id: str, notification_type: str, data: Dict) -> bool:
        """
        Queue a notification for later sending.

        This would typically use a message queue like Redis/RabbitMQ.
        For now, it sends immediately.
        """
        try:
            # In a real implementation, this would be queued
            # For demo purposes, we send immediately

            # Mock user data - in real implementation, get from database
            user_email = f"user_{user_id}@example.com"
            user_name = f"Trader {user_id}"

            if notification_type == 'welcome':
                return self.send_welcome_email(user_email, user_name)
            elif notification_type == 'challenge_funded':
                return self.send_challenge_funded_email(user_email, user_name, data)
            elif notification_type == 'risk_warning':
                return self.send_risk_warning_email(user_email, user_name, data)
            elif notification_type == 'weekly_summary':
                return self.send_weekly_summary_email(user_email, user_name, data)
            elif notification_type == 'payment_confirmation':
                return self.send_payment_confirmation_email(user_email, user_name, data)
            elif notification_type == 'achievement_unlocked':
                return self.send_achievement_unlocked_email(user_email, user_name, data)
            else:
                logger.warning(f"Unknown notification type: {notification_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to queue notification {notification_type} for user {user_id}: {e}")
            return False


# Global notification service instance
notification_service = NotificationService()