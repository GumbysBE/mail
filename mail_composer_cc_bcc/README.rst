================
Email CC and BCC
================

Adds **Cc** and **Bcc** to Odoo's emails. Every recipient gets exactly one
email, and every email shows the same To and Cc, as in a regular mail client.

What each recipient gets
========================

- **To**: one email, visible in To.
- **Cc**: one email, visible in Cc.
- **Bcc**: one email, visible nowhere, not even in the technical headers.
- **Followers** of the document who are not in To or Cc: one email, hidden
  like a Bcc.
- Someone in To and in Cc or Bcc counts as To, and gets one email.
- An internal user in Cc or Bcc gets an email, even when they handle
  notifications in Odoo.
- A recipient without a valid email address does not block the others: only
  that recipient fails.

Features
========

- Cc and Bcc fields in the email composer.
- Default Cc and Bcc per company (*Default Cc* / *Default Bcc* on the company),
  prefilled in the composer.
- A Bcc field on email templates, next to Odoo's Cc. Selecting a template
  replaces the composer's Cc and Bcc with the template's (or the company
  defaults when it has none); unknown addresses become new contacts.
- Automatic emails based on a template, such as the order confirmation, are
  sent with the template's Cc and Bcc, also when the template uses *Default
  Recipients*.
- A reply keeps the Cc and Bcc of the message it answers.
- The Cc and Bcc are stored on the message (*Cc (Partners)*, *Bcc (Partners)*)
  and shown on the email.
- An email is sent the same way immediately, through the email queue, or again
  with *Retry* after a failure.

What it leaves alone
====================

- Messages without Cc or Bcc: Odoo's standard behavior.
- A logged note: never emailed to Cc or Bcc, not even to the company defaults.
- Mass mailing: no Cc or Bcc.
- Emails sent with ``template.send_mail()`` (automations, scheduled actions):
  the template's Cc is sent as in Odoo, its Bcc is ignored.
- The company's default Cc and Bcc only apply to emails a user writes, not to
  automatic ones.

For developers
==============

Another module adds Cc and Bcc by passing them to ``message_post``::

    record.message_post(
        body=body,
        partner_ids=partners_to.ids,
        recipient_cc_ids=partners_cc.ids,
        recipient_bcc_ids=partners_bcc.ids,
        message_type="comment",
        subtype_xmlid="mail.mt_comment",
    )

The why behind each step is in the code comments. Every behavior above is
covered by ``tests/test_mail_cc_bcc_delivery.py``.
