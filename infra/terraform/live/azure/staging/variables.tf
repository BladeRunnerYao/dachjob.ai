variable "name_prefix" {
  description = "Prefix for all Azure resource names"
  type        = string
  default     = "dachjob-staging"
}

variable "location" {
  description = "Azure region for most resources"
  type        = string
  default     = "westeurope"
}

variable "postgres_administrator_password" {
  description = "Password for PostgreSQL administrator"
  type        = string
  sensitive   = true
}

variable "api_image_tag" {
  description = "Docker image tag for the API"
  type        = string
  default     = "latest"
}

variable "frontend_image_tag" {
  description = "Docker image tag for the frontend"
  type        = string
  default     = "latest"
}

variable "worker_image_tag" {
  description = "Docker image tag for the Celery worker"
  type        = string
  default     = "latest"
}

variable "cors_origins" {
  description = "CORS allowed origins for the API"
  type        = string
  default     = ""
}

variable "redis_enabled" {
  description = "Enable Redis at API/worker runtime."
  type        = bool
  default     = true
}

variable "azure_openai_api_key" {
  description = "Azure OpenAI API key. Stored as a Container Apps secret and in Key Vault when provided."
  type        = string
  sensitive   = true
  default     = ""
}

variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint URL."
  type        = string
  default     = ""
}

variable "azure_openai_api_version" {
  description = "Azure OpenAI API version used by the backend."
  type        = string
  default     = "2024-10-21"
}

variable "azure_openai_model_fast" {
  description = "Fast Azure OpenAI deployment/model name."
  type        = string
  default     = "gpt-4o-mini"
}

variable "azure_openai_model_quality" {
  description = "Quality Azure OpenAI deployment/model name."
  type        = string
  default     = "gpt-4o"
}

variable "azure_openai_model_reasoning" {
  description = "Reasoning Azure OpenAI deployment/model name."
  type        = string
  default     = "o1-mini"
}

variable "deepseek_api_key" {
  description = "DeepSeek API key used by Azure Container Apps."
  type        = string
  sensitive   = true
  default     = ""
}

variable "jwt_secret" {
  description = "JWT signing secret for the API."
  type        = string
  sensitive   = true
  default     = ""
}

variable "secret_key" {
  description = "Application secret key."
  type        = string
  sensitive   = true
  default     = ""
}

variable "resend_api_key" {
  description = "Resend API key for transactional email."
  type        = string
  sensitive   = true
  default     = ""
}

variable "resend_from_email" {
  description = "Sender email address used by Resend."
  type        = string
  default     = "onboarding@resend.dev"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    environment = "staging"
    managed_by  = "terraform"
    project     = "dachjob"
  }
}
