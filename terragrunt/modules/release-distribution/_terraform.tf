terraform {
  required_version = "~> 1"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.32"
    }
  }
}

provider "aws" {
  alias  = "east1"
  region = "us-east-1"
}

