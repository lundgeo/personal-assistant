#!/usr/bin/env python3
"""AWS CDK application for Personal Assistant deployment."""
import os
import aws_cdk as cdk
from stack import PersonalAssistantStack

app = cdk.App()

# Get configuration from context or environment
domain_name = app.node.try_get_context("domain_name") or os.environ.get("DOMAIN_NAME", "georgelund.com")
subdomain = app.node.try_get_context("subdomain") or os.environ.get("SUBDOMAIN", "assistant")

PersonalAssistantStack(
    app,
    "PersonalAssistantStack",
    domain_name=domain_name,
    subdomain=subdomain,
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
)

app.synth()
