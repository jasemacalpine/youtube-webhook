#!/usr/bin/env python3
  """
  YouTube Tag Publishing Webhook - Standalone Deployment Version
  Handles Airtable webhooks to publish suggested tags to YouTube videos.
  """

  import os
  import json
  import logging
  import hashlib
  import hmac
  from datetime import datetime
  from typing import Dict, Any, Optional
  from flask import Flask, request, jsonify
  from flask_cors import CORS

  # Google API imports
  from google.auth.transport.requests import Request
  from google.oauth2.credentials import Credentials
  from googleapiclient.discovery import build
  import requests

  # Airtable imports
  from pyairtable import Api

  # Set up logging
  logging.basicConfig(level=logging.INFO)
  logger = logging.getLogger(__name__)

  class YouTubeTagWebhook:
      """Handles webhook requests to publish tags to YouTube."""

      def __init__(self):
          """Initialize with configuration from environment variables."""
          self.airtable_api = Api(os.environ['AIRTABLE_API_KEY'])
          self.airtable_table = self.airtable_api.table(os.environ['AIRTABLE_BASE_ID'], 'Content')
          self.webhook_secret = os.environ.get('WEBHOOK_SECRET', 'dev-secret-key')

          # Initialize YouTube API
          self.youtube = self._init_youtube_api()

      def _init_youtube_api(self):
          """Initialize YouTube API with OAuth2 credentials."""
          try:
              # Create credentials from environment variables
              creds_info = {
                  'token': None,  # Will be refreshed
                  'refresh_token': os.environ['YOUTUBE_REFRESH_TOKEN'],
                  'token_uri': 'https://oauth2.googleapis.com/token',
                  'client_id': os.environ['YOUTUBE_CLIENT_ID'],
                  'client_secret': os.environ['YOUTUBE_CLIENT_SECRET'],
                  'scopes': ['https://www.googleapis.com/auth/youtube.force-ssl']
              }

              creds = Credentials.from_authorized_user_info(creds_info)

              # Refresh token if needed
              if creds.expired:
                  creds.refresh(Request())

              # Build YouTube service
              youtube = build('youtube', 'v3', credentials=creds)
              logger.info("YouTube API initialized successfully")
              return youtube

          except Exception as e:
              logger.error(f"Failed to initialize YouTube API: {e}")
              return None

      def _extract_video_id(self, content_url: str) -> Optional[str]:
          """Extract YouTube video ID from various URL formats."""
          if not content_url:
              return None

          # Handle different YouTube URL formats
          if 'v=' in content_url:
              return content_url.split('v=')[1].split('&')[0]
          elif 'youtu.be/' in content_url:
              return content_url.split('youtu.be/')[1].split('?')[0]
          elif '/embed/' in content_url:
              return content_url.split('/embed/')[1].split('?')[0]

          return None

      def _update_sync_status(self, record_id: str, status: str, error: str = None) -> bool:
          """Update the sync status fields in Airtable."""
          try:
              update_data = {
                  'Tag Sync Status': status,
                  'Last Sync Date': datetime.now().isoformat()
              }

              # Clear or set error message
              if error:
                  update_data['Sync Error'] = error
              else:
                  update_data['Sync Error'] = ''

              # Uncheck Publish Tags if successful
              if status == 'Success':
                  update_data['Publish Tags'] = False

              self.airtable_table.update(record_id, update_data)
              logger.info(f"Updated sync status for {record_id}: {status}")
              return True

          except Exception as e:
              logger.error(f"Failed to update sync status for {record_id}: {e}")
              return False

      def _copy_tags_to_field(self, record_id: str, suggested_tags: str) -> bool:
          """Copy suggested tags to the main tags field."""
          try:
              self.airtable_table.update(record_id, {'Tags': suggested_tags})
              logger.info(f"Copied suggested tags to Tags field for {record_id}")
              return True
          except Exception as e:
              logger.error(f"Failed to copy tags for {record_id}: {e}")
              return False

      def _validate_tags(self, tags: str) -> tuple[bool, str]:
          """Validate tags meet YouTube requirements."""
          if not tags or not tags.strip():
              return False, "No tags provided"

          # YouTube limits: 500 chars total, individual tags max 30 chars
          if len(tags) > 480:  # Leave buffer
              return False, "Tags exceed 500 character limit"

          # Check individual tag lengths
          tag_list = [tag.strip() for tag in tags.split(',')]
          for tag in tag_list:
              if len(tag) > 30:
                  return False, f"Tag '{tag}' exceeds 30 character limit"

          return True, ""

      def _update_youtube_video(self, video_id: str, tags: str) -> tuple[bool, str]:
          """Update YouTube video with new tags."""
          try:
              if not self.youtube:
                  return False, "YouTube API not initialized"

              # Validate tags first
              is_valid, error_msg = self._validate_tags(tags)
              if not is_valid:
                  return False, f"Tag validation failed: {error_msg}"

              # Convert comma-separated tags to list
              tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]

              # Get current video details
              video_response = self.youtube.videos().list(
                  part='snippet',
                  id=video_id
              ).execute()

              if not video_response.get('items'):
                  return False, "Video not found"

              # Update video with new tags
              video_snippet = video_response['items'][0]['snippet']
              video_snippet['tags'] = tag_list

              request = self.youtube.videos().update(
                  part='snippet',
                  body={
                      'id': video_id,
                      'snippet': video_snippet
                  }
              )

              response = request.execute()
              logger.info(f"Successfully updated YouTube video {video_id} with {len(tag_list)} tags")
              return True, f"Updated with {len(tag_list)} tags"

          except Exception as e:
              error_msg = str(e)
              logger.error(f"Failed to update YouTube video {video_id}: {error_msg}")

              # Provide user-friendly error messages
              if "quotaExceeded" in error_msg:
                  return False, "YouTube API quota exceeded. Please try again later."
              elif "videoNotFound" in error_msg:
                  return False, "Video not found on YouTube. Check the video URL."
              elif "forbidden" in error_msg:
                  return False, "Access denied. Check YouTube API permissions."
              else:
                  return False, f"YouTube API error: {error_msg}"

      def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
          """Process the webhook request from Airtable."""
          try:
              # Extract record information
              record_id = webhook_data.get('record_id')
              title = webhook_data.get('title', 'Unknown Title')
              content_url = webhook_data.get('content_url', '')
              suggested_tags = webhook_data.get('suggested_tags', '')

              logger.info(f"Processing webhook for: {title[:50]}...")

              if not record_id:
                  return {'success': False, 'error': 'Missing record_id'}

              # Update status to Processing
              self._update_sync_status(record_id, 'Processing')

              # Validate we have suggested tags
              if not suggested_tags or not suggested_tags.strip():
                  error_msg = "No suggested tags found to publish"
                  self._update_sync_status(record_id, 'Failed', error_msg)
                  return {'success': False, 'error': error_msg}

              # Extract video ID from URL
              video_id = self._extract_video_id(content_url)
              if not video_id:
                  error_msg = "Could not extract video ID from URL"
                  self._update_sync_status(record_id, 'Failed', error_msg)
                  return {'success': False, 'error': error_msg}

              # Copy suggested tags to Tags field
              if not self._copy_tags_to_field(record_id, suggested_tags):
                  error_msg = "Failed to copy tags to Tags field"
                  self._update_sync_status(record_id, 'Failed', error_msg)
                  return {'success': False, 'error': error_msg}

              # Update YouTube video
              youtube_success, youtube_message = self._update_youtube_video(video_id, suggested_tags)

              if youtube_success:
                  # Success!
                  self._update_sync_status(record_id, 'Success')
                  logger.info(f"Successfully published tags for {title[:50]}...")
                  return {
                      'success': True,
                      'message': f'Tags published successfully. {youtube_message}',
                      'video_id': video_id,
                      'tags_count': len([t.strip() for t in suggested_tags.split(',') if t.strip()])
                  }
              else:
                  # YouTube update failed
                  self._update_sync_status(record_id, 'Failed', youtube_message)
                  return {'success': False, 'error': youtube_message}

          except Exception as e:
              error_msg = f"Webhook processing error: {str(e)}"
              logger.error(error_msg)

              if 'record_id' in locals():
                  self._update_sync_status(record_id, 'Failed', error_msg)

              return {'success': False, 'error': error_msg}

  # Create Flask app
  app = Flask(__name__)
  CORS(app)

  # Initialize webhook handler
  webhook_processor = None

  def get_webhook_processor():
      """Get or create webhook processor instance."""
      global webhook_processor
      if webhook_processor is None:
          webhook_processor = YouTubeTagWebhook()
      return webhook_processor

  @app.route('/', methods=['GET'])
  def health_check():
      """Health check endpoint."""
      return jsonify({
          'status': 'healthy',
          'service': 'YouTube Tag Publishing Webhook',
          'message': 'Server is running and ready to receive webhooks'
      })

  @app.route('/webhook', methods=['POST'])
  def handle_webhook():
      """Handle webhook requests from Airtable."""
      try:
          # Get request data
          request_body = request.get_data(as_text=True)
          headers = dict(request.headers)

          logger.info(f"📨 Received webhook request")
          logger.info(f"Body: {request_body}")

          # Parse webhook data
          try:
              webhook_data = json.loads(request_body)
          except json.JSONDecodeError as e:
              return jsonify({'success': False, 'error': f'Invalid JSON: {str(e)}'}), 400

          # Process webhook
          processor = get_webhook_processor()
          result = processor.process_webhook(webhook_data)

          logger.info(f"📤 Webhook result: {result}")

          # Return response
          if result['success']:
              return jsonify({
                  'success': True,
                  'message': result.get('message', 'Tags published successfully'),
                  'data': {
                      'video_id': result.get('video_id'),
                      'tags_count': result.get('tags_count')
                  }
              }), 200
          else:
              return jsonify({
                  'success': False,
                  'error': result.get('error', 'Unknown error')
              }), 400

      except Exception as e:
          logger.error(f"❌ Error handling webhook: {e}")
          return jsonify({
              'success': False,
              'error': f'Server error: {str(e)}'
          }), 500

  if __name__ == '__main__':
      # Get port from environment variable (for deployment platforms)
      port = int(os.environ.get('PORT', 5000))

      print(f"🚀 Starting YouTube Tag Publishing Webhook Server")
      print(f"📡 Port: {port}")
      print(f"🔗 Webhook endpoint: /webhook")
      print(f"💚 Health check: /")

      # Run the server
      app.run(host='0.0.0.0', port=port, debug=False)
