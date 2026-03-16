-- =============================================================================
-- Analytics Query: Per-Provider Performance Report
-- =============================================================================
-- Returns, for each provider within a booking system and date range:
--   • Full provider name
--   • Total appointments handled
--   • Total revenue generated (sum of service prices)
--   • Unique customers served
--   • Average appointment value
-- Results are ordered by total revenue descending.
--
-- Parameters (replace :param with actual values before running):
--   :booking_system_id  → integer  e.g. 1
--   :start_date         → date     e.g. '2026-01-01'
--   :end_date           → date     e.g. '2026-03-07'
-- =============================================================================

SELECT
    CONCAT(p.first_name, ' ', p.last_name)   AS provider_name,
    COUNT(a.id)                               AS total_appointments,
    SUM(s.price)                              AS total_revenue,
    COUNT(DISTINCT a.customer_id)             AS unique_customers,
    ROUND(AVG(s.price), 2)                    AS avg_appointment_value
FROM appointment  a
JOIN provider     p  ON p.id = a.provider_id
JOIN service      s  ON s.id = a.service_id
WHERE
    a.booking_system_id = :booking_system_id
    AND DATE(a.start_time) BETWEEN :start_date AND :end_date
GROUP BY
    a.provider_id,
    p.first_name,
    p.last_name
ORDER BY
    total_revenue DESC;


-- =============================================================================
-- Analytics Query: Per-Service Performance Report
-- =============================================================================
-- Returns, for each service within a booking system and date range:
--   • Service name
--   • Number of times booked
--   • Total revenue generated
--   • Unique customers who booked it
--   • Average price per booking
-- Ordered by total revenue descending.
-- =============================================================================

SELECT
    s.name                                    AS service_name,
    s.duration_minutes,
    s.currency,
    COUNT(a.id)                               AS times_booked,
    SUM(s.price)                              AS total_revenue,
    COUNT(DISTINCT a.customer_id)             AS unique_customers,
    ROUND(AVG(s.price), 2)                    AS avg_price
FROM appointment  a
JOIN service      s  ON s.id = a.service_id
WHERE
    a.booking_system_id = :booking_system_id
    AND DATE(a.start_time) BETWEEN :start_date AND :end_date
GROUP BY
    a.service_id,
    s.name,
    s.duration_minutes,
    s.currency
ORDER BY
    total_revenue DESC;


-- =============================================================================
-- Analytics Query: Monthly Revenue Breakdown
-- =============================================================================
-- Monthly totals for a booking system over a date range.
-- =============================================================================

SELECT
    DATE_FORMAT(a.start_time, '%Y-%m')        AS month,
    COUNT(a.id)                               AS total_appointments,
    COUNT(DISTINCT a.customer_id)             AS unique_customers,
    SUM(s.price)                              AS total_revenue,
    ROUND(AVG(s.price), 2)                    AS avg_appointment_value
FROM appointment  a
JOIN service      s  ON s.id = a.service_id
WHERE
    a.booking_system_id = :booking_system_id
    AND DATE(a.start_time) BETWEEN :start_date AND :end_date
GROUP BY
    DATE_FORMAT(a.start_time, '%Y-%m')
ORDER BY
    month ASC;
