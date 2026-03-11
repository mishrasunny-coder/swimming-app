output "bucket_name" {
  description = "Name of the GCS bucket"
  value       = google_storage_bucket.data.name
}

output "bucket_self_link" {
  description = "Self-link of the GCS bucket"
  value       = google_storage_bucket.data.self_link
}

output "bucket_url" {
  description = "URL of the GCS bucket"
  value       = google_storage_bucket.data.url
}
