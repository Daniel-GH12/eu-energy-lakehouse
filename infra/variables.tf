variable "project_name" {
  description = "Nombre base del proyecto utilizado para nombrar recursos AWS."
  type        = string
  default     = "eu-energy-lakehouse"
}

variable "environment" {
  description = "Entorno de despliegue (por ejemplo, dev o prod)."
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "Región de AWS donde se despliega el Lakehouse."
  type        = string
  default     = "eu-west-1"
}

variable "bucket_name" {
  description = "Nombre globalmente único del bucket S3 para las capas Bronze y Silver."
  type        = string
}

variable "image_tag" {
  description = "Etiqueta de la imagen Docker en ECR ejecutada por AWS Lambda."
  type        = string
  default     = "latest"
}

variable "budget_alert_email" {
  description = "Dirección de correo electrónico para recibir la alerta de presupuesto al 80%."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Tope mensual del presupuesto de AWS Budgets en USD."
  type        = string
  default     = "5"
}
