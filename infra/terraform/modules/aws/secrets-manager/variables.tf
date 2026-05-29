variable "name_prefix" {
  description = "Prefix for secret names"
  type        = string
}

variable "secret_names" {
  description = "List of application secret names (prefix is added automatically)"
  type        = list(string)
  default = [
    "jwt-secret-key",
    "gemini-api-key",
    "deepseek-api-key",
    "openrouter-api-key",
    "google-oauth-client-id",
    "google-oauth-client-secret",
    "smtp-password",
    "s3-access-key",
    "s3-secret-key",
    "test-ci-password",
  ]
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
