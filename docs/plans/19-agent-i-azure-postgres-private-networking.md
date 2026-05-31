# Agent I Plan: Azure PostgreSQL Private Networking

## Mission

Move Azure PostgreSQL access from public networking to private networking while keeping Azure Container Apps able to connect.

This is an Azure Terraform-only task.

## Context

The architecture review identified that Azure PostgreSQL appears to use public network access. This increases exposure and should be replaced with private access.

Relevant resources likely live in:

```text
infra/terraform/modules/azure/networking/
infra/terraform/modules/azure/postgres/
infra/terraform/modules/azure/container-apps/
infra/terraform/live/azure/dev/
```

## Files to Inspect First

```text
infra/terraform/modules/azure/networking/main.tf
infra/terraform/modules/azure/networking/variables.tf
infra/terraform/modules/azure/networking/outputs.tf
infra/terraform/modules/azure/postgres/main.tf
infra/terraform/modules/azure/postgres/variables.tf
infra/terraform/modules/azure/postgres/outputs.tf
infra/terraform/modules/azure/container-apps/main.tf
infra/terraform/modules/azure/container-apps/variables.tf
infra/terraform/modules/azure/container-apps/outputs.tf
infra/terraform/live/azure/dev/main.tf
infra/terraform/live/azure/dev/variables.tf
infra/terraform/live/azure/dev/outputs.tf
```

Search:

```bash
grep -R "public_network_access\|firewall\|private_endpoint\|private_dns\|delegated" infra/terraform/modules/azure infra/terraform/live/azure/dev
```

## Desired End State

- Azure PostgreSQL public network access disabled.
- PostgreSQL reachable from Azure Container Apps through private networking.
- Private DNS is configured so the app can resolve the database hostname.
- No broad `0.0.0.0/0` firewall rule.
- No reliance on "Allow Azure services" as the long-term connectivity model.

## Architecture Options

Choose the option that best matches current Terraform/provider support.

### Option A: Private access with delegated subnet

Use PostgreSQL Flexible Server delegated subnet and private DNS zone.

Typical resources:

- subnet delegated to `Microsoft.DBforPostgreSQL/flexibleServers`
- private DNS zone: `privatelink.postgres.database.azure.com`
- VNet link to private DNS zone
- PostgreSQL flexible server with delegated subnet/private DNS

### Option B: Private endpoint

Use PostgreSQL public server disabled plus private endpoint.

Typical resources:

- private endpoint in VNet subnet
- private DNS zone group
- VNet link
- public network disabled

Prefer Option A if current module already uses Flexible Server private access pattern. Prefer Option B if current module is closer to private endpoint pattern.

## Implementation Steps

### Step 1: Understand current network module

Open:

```text
infra/terraform/modules/azure/networking/main.tf
```

Identify:

- VNet name/id output
- existing subnets
- Container Apps subnet if present
- whether subnet delegation exists

If no DB subnet exists, add one.

Example subnet design:

```text
container-apps-subnet
postgres-subnet
private-endpoints-subnet
```

Do not reuse a subnet with incompatible delegation.

### Step 2: Add PostgreSQL private subnet or private endpoint subnet

If using delegated subnet:

```hcl
resource "azurerm_subnet" "postgres" {
  name                 = "${var.name_prefix}-postgres-subnet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.postgres_subnet_cidr]

  delegation {
    name = "postgres"

    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}
```

If using private endpoint:

```hcl
resource "azurerm_subnet" "private_endpoints" {
  name                 = "${var.name_prefix}-private-endpoints-subnet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.private_endpoints_subnet_cidr]
}
```

Expose subnet IDs as outputs.

### Step 3: Configure private DNS

Add private DNS resources either in networking or postgres module.

Recommended if tightly coupled to Postgres:

```hcl
resource "azurerm_private_dns_zone" "postgres" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = var.resource_group_name
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgres" {
  name                  = "${var.name_prefix}-postgres-dns-link"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.postgres.name
  virtual_network_id    = var.virtual_network_id
}
```

### Step 4: Update PostgreSQL module

Open:

```text
infra/terraform/modules/azure/postgres/main.tf
```

Set public access disabled.

For Flexible Server, expected setting:

```hcl
public_network_access_enabled = false
```

or provider-specific equivalent.

If using delegated subnet/private DNS, set:

```hcl
delegated_subnet_id = var.postgres_subnet_id
private_dns_zone_id = var.postgres_private_dns_zone_id
```

If using private endpoint, add:

```hcl
resource "azurerm_private_endpoint" "postgres" {
  ...
}
```

Remove or disable broad firewall rules.

Do not output passwords.

### Step 5: Ensure Container Apps VNet integration

Open:

```text
infra/terraform/modules/azure/container-apps/main.tf
```

Confirm Container Apps environment is integrated with the VNet/subnet.

If not, add required input:

```hcl
infrastructure_subnet_id = var.container_apps_subnet_id
```

or equivalent supported by the Azure Container Apps Terraform resource.

Ensure `live/azure/dev/main.tf` wires:

```text
networking outputs -> container apps module
networking outputs -> postgres module
```

### Step 6: Update variables and outputs

Add variables where needed:

```hcl
variable "postgres_subnet_cidr" {
  type        = string
  description = "CIDR for Azure PostgreSQL private subnet."
}
```

or:

```hcl
variable "private_endpoints_subnet_cidr" {
  type        = string
  description = "CIDR for Azure private endpoints subnet."
}
```

Add outputs:

```hcl
output "postgres_subnet_id" {
  value = azurerm_subnet.postgres.id
}
```

Do not expose secret values.

### Step 7: Update live Azure dev wiring

Open:

```text
infra/terraform/live/azure/dev/main.tf
```

Wire networking module outputs into postgres and container apps modules.

Example:

```hcl
module "postgres" {
  ...
  virtual_network_id          = module.networking.virtual_network_id
  postgres_subnet_id          = module.networking.postgres_subnet_id
  postgres_private_dns_zone_id = module.networking.postgres_private_dns_zone_id
}
```

Use actual output names from your module.

### Step 8: Remove unsafe public firewall fallback

Search:

```bash
grep -R "0.0.0.0\|Allow Azure\|public_network_access_enabled = true" infra/terraform/modules/azure infra/terraform/live/azure/dev
```

Remove broad rules unless they are required temporarily.

If a temporary rule is unavoidable for migration, it must be:

- clearly commented
- time-bound
- not present in final acceptance state

## Validation Commands

Format:

```bash
terraform fmt -recursive infra/terraform/modules/azure infra/terraform/live/azure/dev
```

Validate:

```bash
terraform -chdir=infra/terraform/live/azure/dev init -backend=false
terraform -chdir=infra/terraform/live/azure/dev validate
```

If Azure credentials are available:

```bash
terraform -chdir=infra/terraform/live/azure/dev plan
```

After apply in dev, verify:

```bash
az postgres flexible-server show --name <server-name> --resource-group <rg> --query publicNetworkAccess
```

Expected:

```text
Disabled
```

Also verify API connectivity:

- Container App starts successfully.
- API health endpoint is healthy.
- API can run DB-backed endpoint.

## Acceptance Criteria

- Azure PostgreSQL public network access is disabled.
- Container Apps can still reach PostgreSQL.
- Private DNS / private endpoint / delegated subnet is configured.
- No `0.0.0.0/0` DB firewall rule remains.
- Terraform validate passes.
- No GCP/AWS Terraform files changed unless shared docs require it.

## Do Not Do

- Do not change AWS or GCP networking.
- Do not change application database code.
- Do not rotate database credentials.
- Do not use broad public firewall rules as final solution.
