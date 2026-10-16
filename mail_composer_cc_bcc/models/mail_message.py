# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools
from odoo.tools import clean_context


class MailMessage(models.Model):
    _inherit = "mail.message"

    recipient_cc_ids = fields.Many2many(
        "res.partner",
        "mail_message_res_partner_cc_rel",
        "mail_message_id",
        "parent_id",
        string="Cc (Partners)",
        context={"active_test": False},
    )
    recipient_bcc_ids = fields.Many2many(
        "res.partner",
        "mail_message_res_partner_bcc_rel",
        "mail_message_id",
        "parent_id",
        string="Bcc (Partners)",
        context={"active_test": False},
    )

    def _has_cc_bcc_audience(self):
        """Whether the emails of this message show only its To and Cc.

        True for any message with Cc / Bcc, and for a user's message with a
        To. Otherwise Odoo's own headers are kept, and so is Reply-All on
        incoming email threads.
        """
        self.ensure_one()
        message = self.sudo()
        return bool(
            message.recipient_cc_ids
            or message.recipient_bcc_ids
            or (message.message_type == "comment" and message.partner_ids)
        )

    def _get_reply_all_audience(self):
        """To, Cc and Bcc of a reply, as Reply-All in a mail client.

        An email received from outside lists its recipients in its headers
        only: its sender and To become To, its Cc stays Cc. The aliases and
        the user replying are left out.
        """
        self.ensure_one()
        message = self.sudo()
        if message.message_type != "email":
            return (
                message.partner_ids,
                message.recipient_cc_ids,
                message.recipient_bcc_ids,
            )
        # The composer's defaults (e.g. its parent message) must not reach the
        # contacts created for unknown addresses: the context is replaced
        Thread = self.env[message.model or "mail.thread"]
        context = clean_context(self.env.context)
        record = Thread.with_context(context).browse(message.res_id)  # pylint: disable=context-overridden
        partners_to, partners_cc = (
            record._partner_find_from_emails_single(
                tools.mail.email_split_and_format(emails or ""), no_create=False
            )
            for emails in (
                f"{message.email_from or ''},{message.incoming_email_to or ''}",
                message.incoming_email_cc,
            )
        )
        replier = self.env.user.partner_id
        return (
            partners_to - partners_cc - replier,
            partners_cc - replier,
            self.env["res.partner"],
        )

    def _get_cc_bcc_audience(self):
        """Split the audience in visible To / Cc and hidden Bcc partners.

        The single place for this rule: the emails are created and sent from
        it, so both steps agree. A partner in To and in Cc / Bcc stays in To.
        """
        self.ensure_one()
        message = self.sudo()
        partners_to = message.partner_ids
        partners_cc = message.recipient_cc_ids - partners_to
        partners_bcc = message.recipient_bcc_ids - partners_to - partners_cc
        return partners_to, partners_cc, partners_bcc
