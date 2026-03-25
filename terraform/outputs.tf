output "data_lake_bucket_name" {
  description = "S3 data lake bucket name"
  value       = aws_s3_bucket.data_lake.bucket
}

output "data_lake_bucket_arn" {
  description = "S3 data lake bucket ARN"
  value       = aws_s3_bucket.data_lake.arn
}

output "s3_raw_path" {
  description = "S3 path for raw data"
  value       = "s3://${aws_s3_bucket.data_lake.bucket}/raw/"
}

output "s3_staging_path" {
  description = "S3 path for staging data"
  value       = "s3://${aws_s3_bucket.data_lake.bucket}/staging/"
}

output "s3_curated_path" {
  description = "S3 path for curated data"
  value       = "s3://${aws_s3_bucket.data_lake.bucket}/curated/"
}
