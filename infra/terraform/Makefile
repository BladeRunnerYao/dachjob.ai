.PHONY: init plan apply destroy fmt validate

ENV ?= dev
TF_DIR = infra/terraform
TFVARS = $(TF_DIR)/environments/$(ENV)/terraform.tfvars
BACKEND_CONF = $(TF_DIR)/environments/$(ENV)/backend.conf

init:
	cd $(TF_DIR) && terraform init -backend-config=$(BACKEND_CONF)

init-local:
	cd $(TF_DIR) && terraform init

plan:
	cd $(TF_DIR) && terraform plan -var-file=$(TFVARS) -out=tfplan

apply:
	cd $(TF_DIR) && terraform apply tfplan

destroy:
	cd $(TF_DIR) && terraform destroy -var-file=$(TFVARS)

fmt:
	cd $(TF_DIR) && terraform fmt -recursive

validate:
	cd $(TF_DIR) && terraform validate

output:
	cd $(TF_DIR) && terraform output
