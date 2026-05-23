variable "name_prefix" {
  type = string
}

variable "location" {
  type = string
}

variable "labels" {
  type    = map(string)
  default = {}
}
