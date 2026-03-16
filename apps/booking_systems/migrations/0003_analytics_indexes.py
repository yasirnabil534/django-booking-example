"""
Migration: 0003_analytics_indexes

Adds composite covering indexes on the appointment table to optimise the
analytics queries in generate_report and queries.sql.

Index strategy
--------------
All analytics queries share the same WHERE clause pattern:

    WHERE booking_system_id = X AND DATE(start_time) BETWEEN Y AND Z

They then GROUP BY or COUNT DISTINCT on one FK column (provider_id,
service_id, or customer_id). A three-column composite index of the form
(booking_system_id, start_time, <fk_col>) allows the database to:

  1. Use booking_system_id as the leading key for a range scan (=)
  2. Use start_time to filter the date range without a full table scan
  3. Read the FK column directly from the index (index-only read for the
     GROUP BY / COUNT DISTINCT) — avoiding a separate lookup into the
     heap / clustered index row.

This reduces per-query I/O from O(n) to O(log n + k) where k is the
number of matching rows.

Indexes added
-------------
idx_appt_analytics_provider
    (booking_system_id, start_time, provider_id)
    Used by: provider-grouped aggregation in generate_report + queries.sql

idx_appt_analytics_service
    (booking_system_id, start_time, service_id)
    Used by: service-grouped aggregation in generate_report + queries.sql
    Also covers the JOIN to service for SUM(price) when the query planner
    chooses to use the index for the driving table scan.

idx_appt_analytics_customer
    (booking_system_id, start_time, customer_id)
    Used by: COUNT(DISTINCT customer_id) in summary + monthly breakdown
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking_systems", "0002_add_last_sync_error"),
    ]

    operations = [
        # Covers provider-grouped analytics:
        # WHERE booking_system_id = X AND start_time BETWEEN Y AND Z
        # GROUP BY provider_id
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["booking_system", "start_time", "provider"],
                name="idx_appt_analytics_provider",
            ),
        ),

        # Covers service-grouped analytics:
        # WHERE booking_system_id = X AND start_time BETWEEN Y AND Z
        # GROUP BY service_id  /  JOIN service ON service.id = a.service_id
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["booking_system", "start_time", "service"],
                name="idx_appt_analytics_service",
            ),
        ),

        # Covers unique-customer counting:
        # COUNT(DISTINCT customer_id) in summary totals and monthly breakdown
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["booking_system", "start_time", "customer"],
                name="idx_appt_analytics_customer",
            ),
        ),
    ]
