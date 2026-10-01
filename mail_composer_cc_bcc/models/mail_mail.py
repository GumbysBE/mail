# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


import os

from odoo import fields, models, tools


def format_emails(partners):
    # Normalized like Odoo's own recipients: the envelope is filtered on them,
    # case-sensitively (see ``send_validated_to`` in ``_prepare_email_message``)
    return [
        tools.formataddr((p.name or "", email))
        for p in partners
        for email in tools.mail.email_normalize_all(p.email)
    ]


def format_emails_raw(partners):
    return [p.email for p in partners if p.email]


def format_emails_str(partners):
    emails = format_emails(partners)
    return ", ".join(emails)


class MailMail(models.Model):
    _inherit = "mail.mail"

    email_bcc = fields.Char("Bcc", help="Blind Cc message recipients")

    def _expose_bcc_marker(self):
        """Whether to also add the informational ``X-Odoo-Bcc`` marker header.

        Disabled by default: the marker survives sending and would expose the
        bcc recipient on every copy. Enable it through the ``expose_x_odoo_bcc``
        context key or the ``EXPOSE_X_ODOO_BCC`` environment variable.
        """
        if self.env.context.get("expose_x_odoo_bcc"):
            return True
        return tools.str2bool(os.environ.get("EXPOSE_X_ODOO_BCC") or "", False)

    def _prepare_outgoing_list(
        self, mail_server=False, recipients_follower_status=None
    ):
        res = super()._prepare_outgoing_list(
            mail_server=mail_server,
            recipients_follower_status=recipients_follower_status,
        )
        # Only set for composer comments: Odoo also posts template notifications
        # (e.g. the order confirmation) through the composer, without Cc / Bcc.
        composer_recipient_ids = self.env.context.get("composer_recipient_ids")
        if not composer_recipient_ids:
            return res

        # Every Cc partner is also a recipient and gets its own email,
        # so Odoo's Cc-only email is always a duplicate here.
        res = [m for m in res if m["email_to"]]

        # The To, Cc headers must be the same on every email, but no record
        # holds the whole audience: partner_ids is empty for followers, and the
        # mail.mail of the other langs are unlinked as they are sent.
        partners_cc_bcc = self.recipient_cc_ids + self.recipient_bcc_ids
        all_recipients = self.env["res.partner"].browse(composer_recipient_ids)
        partner_to = all_recipients - partners_cc_bcc
        email_to = format_emails(partner_to)
        email_to_raw = format_emails_raw(partner_to)
        email_cc = format_emails_str(self.recipient_cc_ids)

        for m in res:
            # Odoo restricts the envelope of each email to its own
            # email_to_normalized, so it still reaches only its recipient once
            # the headers list everyone. Without a valid address that filter is
            # off: keep Odoo's email, which then fails as invalid on its own.
            if not m["partner_id"] or not m["email_to_normalized"]:
                continue

            # The Bcc header only adds the recipient to its own envelope:
            # _prepare_email_message strips it, so it never leaks.
            if m["partner_id"] in self.recipient_bcc_ids:
                # Avoid mutating the shared headers by making a copy
                m["headers"] = {**m["headers"], "Bcc": ", ".join(m["email_to"])}
                # Optional legacy marker. Unlike Bcc it survives sending,
                # so only add it when explicitly enabled (it would expose
                # the bcc recipient otherwise).
                if self._expose_bcc_marker():
                    m["headers"]["X-Odoo-Bcc"] = ", ".join(m["email_to"])

            m.update(
                {
                    "email_to": email_to,
                    "email_to_raw": email_to_raw,
                    "email_cc": email_cc,
                }
            )

        return res
