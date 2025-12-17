# RunPod Deployment Guide for Chatterbox TTS with Voice Cloning

This guide explains how to deploy your custom Chatterbox handler to RunPod.

## Prerequisites

- Docker installed locally
- RunPod account: https://www.runpod.io/
- Docker Hub account (or other container registry)

## Step 1: Build the Docker Image

```bash
cd chatterbox

# Build the image
docker build -f Dockerfile.runpod -t your-dockerhub-username/chatterbox-runpod:latest .

# Login to Docker Hub
docker login

# Push the image
docker push your-dockerhub-username/chatterbox-runpod:latest
```

**Note:** Replace `your-dockerhub-username` with your actual Docker Hub username.

## Step 2: Create RunPod Serverless Endpoint

1. Go to https://www.runpod.io/console/serverless
2. Click "Create Endpoint"
3. Fill in the details:
   - **Endpoint Name**: `chatterbox-voice-cloning`
   - **Container Image**: `your-dockerhub-username/chatterbox-runpod:latest`
   - **GPU Type**: Select a GPU (A4000 or better recommended)
   - **Container Disk**: 10GB minimum
   - **Max Workers**: Start with 1-3
   - **Idle Timeout**: 30 seconds
   - **Execution Timeout**: 180 seconds (3 minutes)

4. Click "Deploy"

## Step 3: Get Your New Endpoint ID

After deployment, you'll see an endpoint ID like: `abc123xyz`

The API URL will be: `https://api.runpod.ai/v2/abc123xyz`

## Step 4: Update Supabase Function

Update the `RUNPOD_ENDPOINT_ID` in your Supabase `generate-audio` function:

```typescript
const RUNPOD_ENDPOINT_ID = "abc123xyz"; // Your new endpoint ID
const RUNPOD_API_URL = `https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}`;
```

## Step 5: Redeploy the Function

```bash
export SUPABASE_ACCESS_TOKEN='your-token'
npx supabase link --project-ref udqfdeoullsxttqguupz
npx supabase functions deploy generate-audio
```

## Step 6: Test Voice Cloning

1. Go to https://historygenai.netlify.app/
2. Upload a voice sample in Settings
3. Generate audio from a YouTube video
4. The audio should now use your cloned voice!

## Monitoring

Monitor your endpoint at: https://www.runpod.io/console/serverless

You can view:
- Request logs
- Execution times
- Error rates
- GPU usage

## Troubleshooting

### Build fails with CUDA errors
- Make sure you're using the correct base image: `runpod/pytorch:2.4.0-py3.11-cuda12.1.0-runtime`

### Container doesn't start
- Check the RunPod logs in the console
- Ensure all dependencies are in `requirements.txt`

### Voice cloning not working
- Check RunPod logs for handler errors
- Verify base64 audio is being decoded correctly
- Ensure reference audio is in WAV or MP3 format

## Cost Optimization

- **Idle Timeout**: Set to 30-60 seconds to balance cold starts vs cost
- **Max Workers**: Start with 1-2, scale up based on demand
- **GPU Selection**: A4000 is cost-effective for this workload
- **Execution Timeout**: 180 seconds should be sufficient for most scripts

## Input Format

The handler expects this JSON input:

```json
{
  "input": {
    "text": "Text to synthesize",
    "reference_audio_base64": "base64_encoded_audio" // optional
  }
}
```

## Output Format

Returns:

```json
{
  "audio_base64": "base64_encoded_wav_audio",
  "sample_rate": 24000
}
```

## Next Steps

1. Test the endpoint directly via RunPod API
2. Monitor performance and adjust GPU/timeout settings
3. Scale workers based on usage patterns
4. Consider adding caching for frequently used voices
