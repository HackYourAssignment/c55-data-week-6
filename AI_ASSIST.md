# AI Assist Report

> Task 7: Fill in all three sections below with specifics. "The AI fixed it"
> is not enough detail. Show the exact prompt you used, paste the suggestion
> you received, and explain what you changed and why.

## The prompt I gave
# AI Assist Report

## Prompt used
I asked ChatGPT for help debugging my Azure Container Apps Job and fixing missing dependencies (psycopg2, Azure Storage connection issues, and pipeline errors).

## Output provided by AI
The AI helped me:
- Fix requirements.txt dependencies
- Fix Docker image build issues
- Retrieve secrets from Azure Key Vault
- Debug Azure Container Apps Job failures
- Verify Blob Storage and Postgres outputs

## What I changed or verified
- Updated requirements.txt with correct versions
- Rebuilt and pushed Docker image
- Retrieved POSTGRES_URL and STORAGE connection string from Key Vault
- Confirmed pipeline runs successfully in Azure
- Verified blob output and execution history