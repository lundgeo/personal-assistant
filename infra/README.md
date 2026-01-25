# AWS Infrastructure for Personal Assistant

This directory contains the AWS CDK infrastructure code for deploying the Personal Assistant application.

## Architecture

- **Frontend**: Static Next.js SPA hosted on S3, served via CloudFront
- **Backend**: Python Flask application running on AWS Lambda
- **Database**: DynamoDB for tool storage
- **API**: API Gateway HTTP API proxied through CloudFront
- **Domain**: Custom domain via Route 53 with ACM certificate

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured with credentials
3. **Node.js** 18+ and npm
4. **Python** 3.11+
5. **Route 53 Hosted Zone** for your domain (georgelund.com)

## Local Deployment

### 1. Install Dependencies

```bash
cd infra
pip install -r requirements.txt
npm install -g aws-cdk
```

### 2. Bootstrap CDK (first time only)

```bash
cdk bootstrap
```

### 3. Deploy

```bash
cdk deploy
```

### 4. Configure API Keys

After deployment, add your LLM API key to the Lambda function:

```bash
# For Claude/Anthropic
aws lambda update-function-configuration \
  --function-name personal-assistant-api \
  --environment "Variables={DATABASE_TYPE=dynamodb,DYNAMODB_TABLE_NAME=personal-assistant-tools,LLM_PROVIDER=claude,ANTHROPIC_MODEL=claude-3-5-sonnet-20241022,TEMPERATURE=0.7,ANTHROPIC_API_KEY=your-api-key-here}"

# For OpenAI
aws lambda update-function-configuration \
  --function-name personal-assistant-api \
  --environment "Variables={DATABASE_TYPE=dynamodb,DYNAMODB_TABLE_NAME=personal-assistant-tools,LLM_PROVIDER=openai,OPENAI_MODEL=gpt-4,TEMPERATURE=0.7,OPENAI_API_KEY=your-api-key-here}"
```

### 5. Deploy Frontend

```bash
cd ../frontend
npm ci
npm run build
aws s3 sync out s3://assistant.georgelund.com-frontend --delete
aws cloudfront create-invalidation --distribution-id <DISTRIBUTION_ID> --paths "/*"
```

## GitHub Actions Deployment

The repository includes a GitHub Actions workflow that automatically deploys on push to `main`.

### Required Secrets

Add these secrets to your GitHub repository:

- `AWS_ROLE_ARN`: ARN of the IAM role for GitHub Actions OIDC
- `AWS_ACCOUNT_ID`: Your AWS account ID

### Setting up OIDC for GitHub Actions

1. Create an OIDC identity provider in IAM for GitHub Actions
2. Create an IAM role with the following trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:<OWNER>/<REPO>:*"
        }
      }
    }
  ]
}
```

3. Attach policies for S3, CloudFront, Lambda, DynamoDB, API Gateway, Route53, ACM, and CloudFormation

## Configuration

### Domain Configuration

Edit `cdk.json` to change the domain:

```json
{
  "context": {
    "domain_name": "yourdomain.com",
    "subdomain": "assistant"
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_TYPE` | Database backend (`sqlite` or `dynamodb`) | `dynamodb` |
| `DYNAMODB_TABLE_NAME` | DynamoDB table name | `personal-assistant-tools` |
| `LLM_PROVIDER` | LLM provider (`claude`, `openai`) | `claude` |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `ANTHROPIC_MODEL` | Anthropic model name | `claude-3-5-sonnet-20241022` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4` |
| `TEMPERATURE` | LLM temperature | `0.7` |

## Stack Outputs

After deployment, the stack outputs:

- `WebsiteURL`: The website URL (https://assistant.georgelund.com)
- `ApiURL`: The API endpoint (https://assistant.georgelund.com/api)
- `CloudFrontDistributionId`: For cache invalidation
- `FrontendBucketName`: S3 bucket for frontend assets
- `LambdaFunctionName`: Lambda function name for configuration

## Cleanup

To destroy the stack:

```bash
cdk destroy
```

Note: This will delete all resources including the DynamoDB tables. Data will be lost.
