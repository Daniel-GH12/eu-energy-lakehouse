output "s3_bucket_name" {
  description = "Nombre del bucket S3 del Lakehouse."
  value       = aws_s3_bucket.lakehouse.bucket
}

output "s3_bucket_arn" {
  description = "ARN del bucket S3 del Lakehouse."
  value       = aws_s3_bucket.lakehouse.arn
}

output "iam_role_arn" {
  description = "ARN del rol IAM con mínimo privilegio asignado a la función Lambda."
  value       = aws_iam_role.lambda_exec.arn
}

output "ecr_repository_url" {
  description = "URL del repositorio ECR para publicar la imagen Docker del pipeline."
  value       = aws_ecr_repository.pipeline.repository_url
}

output "lambda_function_name" {
  description = "Nombre de la función AWS Lambda que ejecuta el pipeline."
  value       = aws_lambda_function.pipeline.function_name
}

output "eventbridge_rule_arn" {
  description = "ARN de la regla diaria de EventBridge (06:00 UTC)."
  value       = aws_cloudwatch_event_rule.daily_ingestion.arn
}
