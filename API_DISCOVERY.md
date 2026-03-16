# API Discovery — Easy!Appointments v1 REST API

**Explored against**: `http://localhost:8888`
**API base path**: `/index.php/api/v1`
**Explored on**: 2026-03-16

---

## Authentication

**Method**: HTTP Basic Authentication

All requests require a username and password sent via the `Authorization: Basic ...` header.

```
GET /index.php/api/v1/providers
Authorization: Basic YWRtaW46YWRtaW4xMjM=
```

| Scenario | HTTP Status | Response |
|---|---|---|
| Valid credentials | `200 OK` | JSON array or object |
| Invalid credentials | `401 Unauthorized` | `You are not authorised to use the API.` (plain text) |
| Missing auth | `401 Unauthorized` | Same plain text |

> **Note**: There is no token/session concept — every request must include credentials.

---

## Available Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/providers` | List all service providers (staff) |
| `GET` | `/providers/{id}` | Get a single provider |
| `POST` | `/providers` | Create a provider |
| `PUT` | `/providers/{id}` | Update a provider |
| `DELETE` | `/providers/{id}` | Delete a provider |
| `GET` | `/customers` | List all customers |
| `GET` | `/customers/{id}` | Get a single customer |
| `POST` | `/customers` | Create a customer |
| `PUT` | `/customers/{id}` | Update a customer |
| `DELETE` | `/customers/{id}` | Delete a customer |
| `GET` | `/services` | List all services |
| `GET` | `/services/{id}` | Get a single service |
| `POST` | `/services` | Create a service |
| `PUT` | `/services/{id}` | Update a service |
| `DELETE` | `/services/{id}` | Delete a service |
| `GET` | `/appointments` | List appointments (filterable by date) |
| `GET` | `/appointments/{id}` | Get a single appointment |
| `POST` | `/appointments` | Create an appointment |
| `PUT` | `/appointments/{id}` | Update an appointment |
| `DELETE` | `/appointments/{id}` | Delete an appointment |
| `GET` | `/admins` | List admin users |
| `GET` | `/secretaries` | List secretary users |
| `GET` | `/settings` | List all system settings |

---

## Pagination

> ⚠️ **Correction from initial discovery**: Easy!Appointments **does** implement server-side pagination with a **default limit of 20 records per request**.

Use `length` + `start` query params to paginate:

| Parameter | Type | Description |
|---|---|---|
| `length` | integer | Number of records to return (e.g. `500`) |
| `start` | integer | Offset — number of records to skip (e.g. `0`, `500`, `1000`) |

```http
GET /index.php/api/v1/appointments?length=500&start=0
GET /index.php/api/v1/appointments?length=500&start=500
```

Fetch pages until a response with fewer than `length` records is returned — that's the last page.

> The `BookingSystemClient` handles this automatically with `_PAGE_SIZE = 500`.

---

## Field Naming Conventions

All fields use **camelCase**:

| Domain | camelCase fields |
|---|---|
| Provider | `id`, `firstName`, `lastName`, `email`, `phone`, `mobile`, `timezone`, `language`, `services`, `settings` |
| Customer | `id`, `firstName`, `lastName`, `email`, `phone`, `mobile`, `address`, `city`, `state`, `zip`, `notes`, `timezone`, `language` |
| Service | `id`, `name`, `duration`, `price`, `currency`, `description`, `attendantsNumber`, `categoryId` |
| Appointment | `id`, `book`, `start`, `end`, `location`, `notes`, `status`, `customerId`, `providerId`, `serviceId`, `googleCalendarId`, `caldavCalendarId` |

---

## Response Formats

### List response
```json
[
  { "id": 4, "firstName": "Sarah", "lastName": "Johnson", ... },
  { "id": 5, "firstName": "Mike", "lastName": "Chen", ... }
]
```

### Single resource response
```json
{ "id": 4, "firstName": "Sarah", "lastName": "Johnson", ... }
```

### Error response (`4xx`)
```
You are not authorised to use the API.
```
> Errors are returned as **plain text**, not JSON.

---

## Date Filtering (Appointments)

Appointments support date-range filtering via query parameters:

| Parameter | Format | Example |
|---|---|---|
| `start_datetime` | `YYYY-MM-DD HH:MM:SS` | `2026-01-05 00:00:00` |
| `end_datetime` | `YYYY-MM-DD HH:MM:SS` | `2026-01-05 23:59:59` |

```http
GET /index.php/api/v1/appointments?start_datetime=2026-01-05+00:00:00&end_datetime=2026-01-05+23:59:59
```

---

## Appointment `status` Field

The `status` field on appointments is an **empty string `""`** by default when a booking is created. It does not use a defined enum. The field appears intended for custom status labels.

---

## Rate Limiting

- **429 Too Many Requests** is returned under heavy load (observed during bulk seeding of ~800 appointments)
- No `Retry-After` header is guaranteed to be present
- **Recommended strategy**: on 429, wait 30 seconds and retry the same request

---

## Quirks & Notes

1. **Field name mismatch**: The `Provider` response includes a `mobile` field not present in the POST body schema
2. **Service `duration`**: Returned as integer minutes (e.g. `30`), not a duration string
3. **No Content-Range or X-Total-Count headers**: No way to know total count from headers alone
4. **`book` field on Appointment**: A `DateTime` field (`"book": "2026-03-15 05:14:40"`) representing when the appointment was created — this is not documented in the official schema
5. **Provider `settings.workingPlan`**: A nested object with per-day schedules; `null` for Sunday means closed
6. **`categories` endpoint**: Returns `404` — despite being referenced in docs, it appears unavailable in this version
7. **Plain-text errors**: All error responses are plain text, not JSON — JSON parsing will fail on error responses

---

## Provider — Full Sample Response

```json
{
  "id": 4,
  "firstName": "Sarah",
  "lastName": "Johnson",
  "email": "sarah@testsalon.com",
  "mobile": null,
  "phone": "+1-555-0101",
  "address": null,
  "city": null,
  "state": null,
  "zip": null,
  "notes": null,
  "timezone": "America/New_York",
  "language": "english",
  "services": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
  "settings": {
    "username": "sarahjohnson",
    "notifications": true,
    "calendarView": "default",
    "workingPlan": {
      "monday": { "start": "09:00", "end": "18:00", "breaks": [{ "start": "12:00", "end": "13:00" }] },
      "sunday": null
    }
  }
}
```

## Appointment — Full Sample Response

```json
{
  "id": 1,
  "book": "2026-03-15 05:14:40",
  "start": "2026-01-05 09:00:00",
  "end": "2026-01-05 09:55:00",
  "location": "Test Salon - Main Branch",
  "notes": null,
  "status": "",
  "customerId": 23,
  "providerId": 4,
  "serviceId": 7,
  "googleCalendarId": null,
  "caldavCalendarId": null
}
```
