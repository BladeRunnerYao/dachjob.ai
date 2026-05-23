variable "name_prefix" {
  type = string
}

variable "project_id" {
  type = string
}

variable "billing_account_id" {
  type = string
}

variable "budget_amount" {
  type = number
}

variable "notification_email" {
  type = string
}

variable "cloud_run_api_url" {
  type = string
}

variable "labels" {
  type    = map(string)
  default = {}
}
