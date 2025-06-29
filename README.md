# YouTube Tag Publishing Webhook

A webhook service that automatically publishes suggested tags to YouTube videos when triggered from Airtable.

## Features

- 🎯 **Real-time Tag Publishing**: Automatically updates YouTube video tags when Airtable checkbox is checked
- 🔄 **Status Tracking**: Updates sync status and error messages in real-time
- ✅ **Tag Validation**: Ensures tags meet YouTube requirements (500 char limit, 30 char per tag)
- 🛡️ **Error Handling**: Comprehensive error handling with user-friendly messages
- 📊 **Logging**: Detailed logging for debugging and monitoring

## Deployment

### Railway (Recommended)

1. **Create Railway Project**:
   ```bash
   # Connect to GitHub repository
   railway login
   railway link
   ```

2. **Set Environment Variables**:
   ```bash
   # Airtable Configuration
   railway variables set AIRTABLE_API_KEY="your_airtable_api_key"
   railway variables set AIRTABLE_BASE_ID="your_base_id"
   
   # YouTube OAuth2 Configuration
   railway variables set YOUTUBE_CLIENT_ID="your_youtube_client_id"
   railway variables set YOUTUBE_CLIENT_SECRET="your_youtube_client_secret"
   railway variables set YOUTUBE_REFRESH_TOKEN="your_refresh_token"
   
   # Optional
   railway variables set WEBHOOK_SECRET="your_webhook_secret"
   ```

3. **Deploy**:
   ```bash
   railway up
   ```

### Heroku

1. **Create Heroku App**:
   ```bash
   heroku create youtube-webhook-app
   ```

2. **Set Environment Variables**:
   ```bash
   heroku config:set AIRTABLE_API_KEY="your_airtable_api_key"
   heroku config:set AIRTABLE_BASE_ID="your_base_id"
   heroku config:set YOUTUBE_CLIENT_ID="your_youtube_client_id"
   heroku config:set YOUTUBE_CLIENT_SECRET="your_youtube_client_secret"
   heroku config:set YOUTUBE_REFRESH_TOKEN="your_refresh_token"
   ```

3. **Deploy**:
   ```bash
   git push heroku main
   ```

### Vercel

1. **Install Vercel CLI**:
   ```bash
   npm i -g vercel
   ```

2. **Deploy**:
   ```bash
   vercel --prod
   ```

3. **Set Environment Variables** in Vercel dashboard

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AIRTABLE_API_KEY` | Your Airtable API key | ✅ |
| `AIRTABLE_BASE_ID` | Your Airtable base ID | ✅ |
| `YOUTUBE_CLIENT_ID` | YouTube OAuth2 client ID | ✅ |
| `YOUTUBE_CLIENT_SECRET` | YouTube OAuth2 client secret | ✅ |
| `YOUTUBE_REFRESH_TOKEN` | YouTube OAuth2 refresh token | ✅ |
| `WEBHOOK_SECRET` | Optional webhook validation secret | ❌ |
| `PORT` | Server port (auto-set by platform) | ❌ |

## API Endpoints

### `GET /`
Health check endpoint
```json
{
  "status": "healthy",
  "service": "YouTube Tag Publishing Webhook",
  "message": "Server is running and ready to receive webhooks"
}
```

### `POST /webhook`
Main webhook endpoint for Airtable automation

**Request Body**:
```json
{
  "record_id": "recXXXXXXXXXXXXXX",
  "title": "Video Title",
  "content_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "suggested_tags": "tag1, tag2, tag3"
}
```

**Success Response**:
```json
{
  "success": true,
  "message": "Tags published successfully. Updated with 3 tags",
  "data": {
    "video_id": "VIDEO_ID",
    "tags_count": 3
  }
}
```

**Error Response**:
```json
{
  "success": false,
  "error": "Error message describing what went wrong"
}
```

## Airtable Integration

### Required Fields

Your Airtable `Content` table should have these fields:

- `Publish Tags` (Checkbox) - Triggers the webhook when checked
- `Tags` (Single line text) - Where suggested tags are copied
- `Suggested Tags` (Single line text) - SEO-optimized tags to publish
- `Tag Sync Status` (Single select) - Status tracking (Processing, Success, Failed)
- `Last Sync Date` (Date & time) - Timestamp of last sync attempt
- `Sync Error` (Long text) - Error messages if sync fails
- `Content URL` (URL) - YouTube video URL

### Automation Script

Create an Airtable automation with this script:

```javascript
// Get the record that triggered this automation
let inputConfig = input.config();
let recordId = inputConfig.recordId;

// Fetch the full record data
let table = base.getTable('Content');
let record = await table.selectRecordAsync(recordId);

// Prepare webhook payload
let webhookData = {
    record_id: recordId,
    title: record.getCellValue('Title') || 'Unknown Title',
    content_url: record.getCellValue('Content URL') || '',
    suggested_tags: record.getCellValue('Suggested Tags') || ''
};

// Your webhook URL (replace with your deployed URL)
let webhookUrl = "https://your-webhook-url.railway.app/webhook";

// Send webhook request
let response = await fetch(webhookUrl, {
    method: "POST",
    headers: {
        "Content-Type": "application/json"
    },
    body: JSON.stringify(webhookData)
});

console.log(`Webhook sent. Status: ${response.status}`);
if (!response.ok) {
    let errorText = await response.text();
    console.log(`Error: ${errorText}`);
}
```

## Testing

### Local Testing

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**:
   ```bash
   export AIRTABLE_API_KEY="your_key"
   export AIRTABLE_BASE_ID="your_base_id"
   # ... other variables
   ```

3. **Run Server**:
   ```bash
   python app.py
   ```

4. **Test Webhook**:
   ```bash
   curl -X POST http://localhost:5000/webhook \
     -H "Content-Type: application/json" \
     -d '{
       "record_id": "test123",
       "title": "Test Video",
       "content_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
       "suggested_tags": "test, webhook, automation"
     }'
   ```

## Monitoring

- **Health Check**: `GET /` returns server status
- **Logs**: Check deployment platform logs for webhook processing details
- **Airtable Status**: Monitor `Tag Sync Status` field for real-time updates

## Troubleshooting

### Common Issues

1. **"YouTube API not initialized"**
   - Check OAuth2 credentials are correct
   - Ensure refresh token has proper scopes

2. **"Video not found"**
   - Verify YouTube URL format is correct
   - Check video is not private/unlisted

3. **"Tags exceed limit"**
   - YouTube allows max 500 characters total
   - Individual tags max 30 characters

4. **"Access denied"**
   - Verify YouTube API credentials have write permissions
   - Check the video belongs to the authenticated channel

### Debug Mode

For detailed debugging, check the server logs after each webhook request. The service logs all major steps including:
- Webhook received
- Record processing status
- YouTube API responses
- Airtable updates

## License

MIT License - see LICENSE file for details.