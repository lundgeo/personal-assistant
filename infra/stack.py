"""AWS CDK Stack for Personal Assistant application."""
from constructs import Construct
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_lambda as lambda_,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_dynamodb as dynamodb,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_iam as iam,
)


class PersonalAssistantStack(Stack):
    """CDK Stack for deploying the Personal Assistant application to AWS."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        domain_name: str,
        subdomain: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        full_domain = f"{subdomain}.{domain_name}"

        # =====================================================
        # DynamoDB Tables
        # =====================================================

        # Tools table
        tools_table = dynamodb.Table(
            self,
            "ToolsTable",
            table_name="personal-assistant-tools",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.NUMBER
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # Change to RETAIN for production
        )

        # Add GSI for querying by name
        tools_table.add_global_secondary_index(
            index_name="name-index",
            partition_key=dynamodb.Attribute(
                name="name",
                type=dynamodb.AttributeType.STRING
            ),
        )

        # Counter table for auto-increment IDs
        counter_table = dynamodb.Table(
            self,
            "CounterTable",
            table_name="personal-assistant-tools-counters",
            partition_key=dynamodb.Attribute(
                name="counter_name",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # =====================================================
        # Lambda Function
        # =====================================================

        # Lambda function for the backend API
        backend_lambda = lambda_.Function(
            self,
            "BackendLambda",
            function_name="personal-assistant-api",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_handler.handler",
            code=lambda_.Code.from_asset(
                "../backend",
                exclude=[
                    "*.pyc",
                    "__pycache__",
                    ".venv",
                    "*.db",
                    ".env",
                    "mcp_servers.json",
                ],
            ),
            timeout=Duration.seconds(300),
            memory_size=512,
            environment={
                "DATABASE_TYPE": "dynamodb",
                "DYNAMODB_TABLE_NAME": tools_table.table_name,
                # LLM configuration - set defaults, override via AWS Console/CLI
                "LLM_PROVIDER": "claude",
                "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
                "TEMPERATURE": "0.7",
                # API keys should be added manually after deployment:
                # aws lambda update-function-configuration \
                #   --function-name personal-assistant-api \
                #   --environment "Variables={...,ANTHROPIC_API_KEY=your-key}"
            },
        )

        # Grant Lambda permissions to DynamoDB
        tools_table.grant_read_write_data(backend_lambda)
        counter_table.grant_read_write_data(backend_lambda)

        # =====================================================
        # API Gateway
        # =====================================================

        # HTTP API Gateway
        http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            api_name="personal-assistant-api",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigwv2.CorsHttpMethod.ANY],
                allow_headers=["*"],
            ),
        )

        # Lambda integration
        lambda_integration = integrations.HttpLambdaIntegration(
            "LambdaIntegration",
            backend_lambda,
        )

        # Add routes - proxy all requests to Lambda
        http_api.add_routes(
            path="/{proxy+}",
            methods=[apigwv2.HttpMethod.ANY],
            integration=lambda_integration,
        )

        # Also add root route
        http_api.add_routes(
            path="/",
            methods=[apigwv2.HttpMethod.ANY],
            integration=lambda_integration,
        )

        # =====================================================
        # Route 53 Hosted Zone (lookup existing)
        # =====================================================

        hosted_zone = route53.HostedZone.from_lookup(
            self,
            "HostedZone",
            domain_name=domain_name,
        )

        # =====================================================
        # ACM Certificate (must be in us-east-1 for CloudFront)
        # =====================================================

        certificate = acm.Certificate(
            self,
            "Certificate",
            domain_name=full_domain,
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )

        # =====================================================
        # S3 Bucket for Frontend
        # =====================================================

        frontend_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            bucket_name=f"{full_domain}-frontend",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # =====================================================
        # CloudFront Distribution
        # =====================================================

        # Origin Access Identity for S3
        oai = cloudfront.OriginAccessIdentity(
            self,
            "OAI",
            comment=f"OAI for {full_domain}",
        )

        # Grant read access to CloudFront
        frontend_bucket.grant_read(oai)

        # CloudFront Function to strip /api prefix
        strip_api_prefix_function = cloudfront.Function(
            self,
            "StripApiPrefixFunction",
            code=cloudfront.FunctionCode.from_inline("""
function handler(event) {
    var request = event.request;
    // Strip /api prefix from the URI
    if (request.uri.startsWith('/api')) {
        request.uri = request.uri.replace(/^\\/api/, '') || '/';
    }
    return request;
}
"""),
            runtime=cloudfront.FunctionRuntime.JS_2_0,
        )

        # CloudFront distribution
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    frontend_bucket,
                    origin_access_identity=oai,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        f"{http_api.http_api_id}.execute-api.{self.region}.amazonaws.com",
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    function_associations=[
                        cloudfront.FunctionAssociation(
                            function=strip_api_prefix_function,
                            event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                        ),
                    ],
                ),
            },
            domain_names=[full_domain],
            certificate=certificate,
            default_root_object="index.html",
            error_responses=[
                # Handle SPA routing - return index.html for 404s
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
        )

        # =====================================================
        # Route 53 Record
        # =====================================================

        route53.ARecord(
            self,
            "AliasRecord",
            zone=hosted_zone,
            record_name=subdomain,
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            ),
        )

        # =====================================================
        # Outputs
        # =====================================================

        CfnOutput(
            self,
            "WebsiteURL",
            value=f"https://{full_domain}",
            description="Website URL",
        )

        CfnOutput(
            self,
            "ApiURL",
            value=f"https://{full_domain}/api",
            description="API URL",
        )

        CfnOutput(
            self,
            "CloudFrontDistributionId",
            value=distribution.distribution_id,
            description="CloudFront Distribution ID (for cache invalidation)",
        )

        CfnOutput(
            self,
            "FrontendBucketName",
            value=frontend_bucket.bucket_name,
            description="S3 Bucket for frontend assets",
        )

        CfnOutput(
            self,
            "LambdaFunctionName",
            value=backend_lambda.function_name,
            description="Lambda function name",
        )
