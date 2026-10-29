# My real-platform practice plan

I keep my optional platform exercises separate from my working local simulation. The steps below describe the account-level practice I still need to complete and verify.

The local prototype runs without accounts. These optional exercises turn the simulation into genuine platform practice in your own accounts. They have not been completed on your behalf. Do not describe the adapters as a connected production integration.

## Shopify development store

Shopify documents development stores for testing and states that real transactions are not supported. Use a development store through its developer tools, rather than upgrading to a paid merchant plan for this exercise.

Official guidance:

- https://shopify.dev/docs/apps/build/stores/development-stores
- https://help.shopify.com/en/manual/products/import-export/using-csv
- https://shopify.dev/docs/api/admin-graphql/2026-10/queries/products

1. Create your own dev store in Shopify's Dev Dashboard. Select test data or a development configuration suited to a merchandise demo. Keep the storefront private while practising.
2. Inspect `examples/Shopify_Products.csv`. It contains the 16 fictional products, approved demo prices, and current-format Shopify columns. Every product is **draft**. Import it into an empty dev store with **Products → Import**. Review the import preview. This file is for new demo products, not overwriting an employer's catalog.
3. Complete APP-003's description and HAT-001's alt text in the actual Shopify admin. Show bulk editing and single-product editing. Capture your own evidence after completing the exercise.
4. Product image URL fields are intentionally blank: localhost image URLs are inaccessible to Shopify. Upload your own original product imagery in a Shopify-supported image format, or use the supplied PNG illustration exports in `examples/shopify-images/` if present. The local SVG illustrations are also available for conversion. Product imagery in Shopify is a separate platform step.
5. Create manual collections matching Everyday Collection, Gift Edit, and Winter Collection. Review their merchandising order, descriptions, and mobile appearance in the platform's theme preview. The CSV's Tags field is a grouping aid; it does not create these collections automatically.
6. Set quantities at your development location. The product CSV deliberately omits inventory quantity so it does not assume a single-location inventory configuration. Use the admin inventory editor, or export and edit the correct location-specific inventory template.
7. Create a development discount matching the intended 10% promotion and apply it only to the appropriate collection. The local MAPLE10 database row does not create a Shopify discount.
8. Activate only the demo products you want to show, publish them to the development storefront's sales channel, and use an approved test payment gateway to place test orders. Do not use real card charges.
9. Complete a Shopify test order's fulfillment workflow and inspect its platform reports. Reconcile export definitions with the project's documented merchandise revenue metric.

The local app and Shopify are separate stores. Manual platform changes do not automatically update the local prototype.

### Optional product extract

Create/install an app for your own development store using the current Shopify app workflow. Grant only the scopes needed to read product and inventory information. Obtain an Admin API access token through the app's supported authentication process. Token issuance depends on the app/store setup; do not use a storefront token for Admin GraphQL calls.

Set `SHOPIFY_STORE_DOMAIN` and `SHOPIFY_ACCESS_TOKEN` in your terminal environment. Run:

```bash
python -m merchops.integrations shopify-read --output live-data/shopify_products.json
```

The adapter uses GraphQL Admin API **2026-10**, follows product cursors, and refuses silently incomplete variant exports above its 100-variant-per-product scope. It has no product mutation or order-writing endpoint. A real request still needs account validation. The result stays in a staging file and does not replace the synthetic database.

## Google Analytics 4

Official guidance:

- https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart
- https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema
- https://developers.google.com/analytics/devguides/collection/ga4/ecommerce

The local storefront records session funnel events in SQLite. It does **not** send them to Google Analytics and is not already instrumented with a GA4 property.

For platform practice, use your own test property's authorized ecommerce integration or implement Google's documented events on a separate test site. Review `view_item`, `add_to_cart`, `begin_checkout`, `purchase`, and `refund`, their item/currency parameters, and transaction deduplication. Observe events in DebugView and then verify reports after normal processing delays. Do not claim that naming local events the same way proves GA4 tagging is working.

For a read-only report, enable the Analytics Data API, authorize an account with access to your GA4 property, and obtain a short-lived OAuth access token with the appropriate analytics read scope. Set `GA4_PROPERTY_ID` and `GA4_ACCESS_TOKEN` in your terminal, then run:

```bash
python -m merchops.integrations ga4-read --start 2026-10-01 --end 2026-10-26 --output live-data/ga4_report.json
```

It requests daily channel sessions, purchase events, and purchase revenue in CAD. It handles pagination and preserves the distinction between purchase events and purchasing sessions. Account authorization, metric compatibility on your property, tracking implementation, and real report results remain unverified here.

## Klaviyo and CRM

Official guidance:

- https://developers.klaviyo.com/en/reference/get_profiles
- https://developers.klaviyo.com/en/reference/create_or_update_profile

The working local CRM exercise shows segmentation, consent suppression, cart-reminder eligibility, and draft copy. `examples/Klaviyo_Profile_Preview.json` shows the shape of profile import payloads using fictional example.com identities. It does not subscribe profiles and must not be used to send to those fake addresses.

If you use your own test account, review its subscription and suppression controls, create a test list with an email address you own and have chosen to use, and build a draft flow. Inspect desktop/mobile previews and a working unsubscribe mechanism. Importing a profile or setting a custom consent property is not the same as granting marketing subscription consent in the platform. No campaign is sent by this project.

For the optional read-only adapter, create a private API key with `profiles:read`, set `KLAVIYO_PRIVATE_API_KEY` in your terminal, and run:

```bash
python -m merchops.integrations klaviyo-read --output live-data/klaviyo_profiles.json
```

The pinned API revision is **2026-10-15**. The adapter follows only Klaviyo HTTPS profile pagination links and requests subscription information. Live authentication and behavior have not been tested. Treat account exports as private and keep them out of a public portfolio repository.

## What counts as completed evidence

Keep a concise record of what you actually did: date, test store/property, operation, expected result, actual result, and evidence location. Distinguish a local simulation, a mocked adapter test, and a verified action in the real platform. Do not claim a live integration, actual paid campaign, or business impact until you have completed and measured it.
