from __future__ import annotations

import pandas as pd
import streamlit as st

from app.core.config import get_settings
from app.services.discovery.youtube_client import YouTubeAPIError
from app.services.llm.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
    MessageValidationError,
)
from app.services.outreach.exceptions import (
    DuplicateOutreachError,
    OutreachConfigurationError,
    OutreachDeliveryError,
    OutreachOutcomeUnknown,
)
from dashboard import data

st.set_page_config(
    page_title="Micro-Influencer Outreach",
    page_icon="📣",
    layout="wide",
)


def _show_error(error: Exception) -> None:
    st.error(str(error))


def _render_discovery() -> None:
    st.header("Discover influencers")
    st.caption(
        "Import a permitted CSV source or search public YouTube channel data."
    )
    csv_tab, youtube_tab = st.tabs(["Import CSV", "YouTube Data API"])

    with csv_tab:
        uploaded = st.file_uploader(
            "Upload influencer CSV",
            type=["csv"],
            help="Required columns: platform and username.",
            key="influencer_csv",
        )
        if uploaded is not None and st.button(
            "Import CSV",
            type="primary",
            key="import_csv",
        ):
            try:
                report = data.import_csv_content(uploaded.getvalue())
            except (ValueError, OSError) as exc:
                _show_error(exc)
            else:
                st.success(
                    f"Imported {report['imported']} of {report['total_rows']} "
                    f"rows. Duplicates: {report['duplicates']}; "
                    f"invalid rows: {report['invalid']}."
                )
                if report["errors"]:
                    st.dataframe(
                        pd.DataFrame(report["errors"]),
                        use_container_width=True,
                        hide_index=True,
                    )

    with youtube_tab:
        st.info(
            "Uses the configured YouTube Data API key and quota. "
            "Discovered profiles may have unavailable metrics."
        )
        with st.form("youtube_discovery"):
            query = st.text_input(
                "Channel search query",
                value="fitness creators",
            )
            pages = st.number_input(
                "Search pages (up to 50 channels per page)",
                min_value=1,
                max_value=5,
                value=1,
                step=1,
            )
            submitted = st.form_submit_button(
                "Search YouTube",
                type="primary",
            )
        if submitted:
            try:
                report = data.discover_youtube(query, int(pages))
            except (YouTubeAPIError, ValueError) as exc:
                _show_error(exc)
            else:
                st.success(
                    f"Found {report['channel_ids']} channels; imported "
                    f"{report['imported']} new profiles. "
                    f"Duplicates: {report['duplicates']}."
                )


def _render_influencers() -> None:
    st.header("Influencers")
    controls = st.columns((2, 1, 1))
    search = controls[0].text_input(
        "Search name, username, niche or bio",
        key="influencer_search",
    )
    platforms = ["All", "youtube", "instagram"]
    platform = controls[1].selectbox("Platform", platforms)
    qualification_filter = controls[2].selectbox(
        "Qualification",
        ["All", "accepted", "rejected", "needs_review"],
    )

    rows = data.list_influencers(search=search, platform=platform)
    records = []
    for creator, qualification in rows:
        if (
            qualification_filter != "All"
            and qualification["overall_status"] != qualification_filter
        ):
            continue
        records.append(
            {
                "Name": creator.display_name or creator.username,
                "Username": creator.username,
                "Platform": creator.platform,
                "Followers": creator.followers_count,
                "Niche": creator.niche,
                "Email": creator.email,
                "Qualification": qualification["overall_status"],
                "Reason": (
                    qualification["filter_reasons"]
                    or [qualification["niche_reason"]]
                ),
                "Profile": creator.profile_url,
                "Source": creator.source,
            }
        )

    st.metric("Profiles", len(records))
    if records:
        st.dataframe(
            pd.DataFrame(records),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Profile": st.column_config.LinkColumn("Profile"),
                "Followers": st.column_config.NumberColumn(format="%d"),
            },
        )
    else:
        st.info("No profiles match these filters yet. Import or discover creators.")

    export_rows = data.influencers_export_rows()
    if export_rows:
        st.download_button(
            "Download influencer CSV",
            data=pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8"),
            file_name="influencers.csv",
            mime="text/csv",
        )


def _render_messages() -> None:
    st.header("Messages & review")
    with st.expander("Create campaign", expanded=not bool(data.list_campaigns())):
        with st.form("create_campaign"):
            name = st.text_input("Campaign name")
            niche = st.selectbox("Campaign niche", ["fitness"])
            description = st.text_area("Campaign description")
            create = st.form_submit_button("Create campaign")
        if create:
            if not name.strip():
                st.error("Campaign name is required.")
            else:
                data.create_campaign(name, niche, description)
                st.success("Campaign created.")
                st.rerun()

    campaigns = data.list_campaigns()
    if not campaigns:
        st.info("Create a campaign to generate messages.")
        return

    st.caption(
        "The current qualification pipeline supports fitness creators; "
        "only accepted profiles receive generated drafts."
    )
    campaign = st.selectbox(
        "Campaign",
        campaigns,
        format_func=lambda item: f"{item.name} · {item.niche}",
    )
    if st.button(
        "Generate messages for qualified creators",
        type="primary",
        key=f"generate_{campaign.id}",
    ):
        try:
            messages = data.generate_campaign_messages(campaign.id)
        except (
            LookupError,
            LLMConfigurationError,
            LLMProviderError,
            MessageValidationError,
        ) as exc:
            _show_error(exc)
        else:
            st.success(f"Ready for review: {len(messages)} messages.")
            st.rerun()

    creator_messages = data.list_campaign_messages(campaign.id)
    if not creator_messages:
        st.info("No messages for this campaign yet.")
        return

    for message, creator in creator_messages:
        name = creator.display_name or creator.username
        label = f"{name} · {message.channel} · {message.status}"
        with st.expander(label):
            st.caption(
                f"Message #{message.id} · "
                f"{creator.email or 'No email recorded'}"
            )
            if message.status == "draft":
                with st.form(f"edit_message_{message.id}"):
                    subject = (
                        st.text_input(
                            "Email subject",
                            value=message.subject or "",
                        )
                        if message.channel == "email"
                        else None
                    )
                    body = st.text_area("Message", value=message.body, height=180)
                    save = st.form_submit_button("Save edits")
                if save:
                    try:
                        data.update_draft(message.id, subject, body)
                    except (LookupError, ValueError) as exc:
                        _show_error(exc)
                    else:
                        st.success("Draft saved and logged.")
                        st.rerun()
                if st.button(
                    "Approve message",
                    key=f"approve_{message.id}",
                    type="primary",
                ):
                    try:
                        data.approve_message(message.id)
                    except (LookupError, ValueError) as exc:
                        _show_error(exc)
                    else:
                        st.success("Message approved.")
                        st.rerun()
            else:
                if message.subject:
                    st.markdown(f"**Subject:** {message.subject}")
                st.write(message.body)
                if message.approved_at:
                    st.caption(f"Approved at {message.approved_at}")


def _render_outreach() -> None:
    st.header("Outreach tracker")
    st.warning(
        "Real email is sent only after approval and explicit configuration. "
        "Instagram messages must be sent manually."
    )
    records = data.list_campaign_messages()
    if not records:
        st.info("No outreach messages have been generated.")
    for message, creator in records:
        name = creator.display_name or creator.username
        with st.expander(
            f"{name} · {message.channel} · {message.status} · #{message.id}"
        ):
            st.caption(
                f"Campaign #{message.campaign_id} · "
                f"{creator.email or 'No email recorded'}"
            )
            if message.subject:
                st.markdown(f"**{message.subject}**")
            st.write(message.body)

            if message.channel == "email" and message.status in {
                "approved",
                "dry_run",
                "failed",
            }:
                if message.status in {"approved", "failed"} and st.button(
                    "Record dry run",
                    key=f"dry_run_{message.id}",
                ):
                    try:
                        data.dry_run_message(message.id)
                    except (LookupError, ValueError, DuplicateOutreachError) as exc:
                        _show_error(exc)
                    else:
                        st.success("Dry-run recorded.")
                        st.rerun()

                allow_send = get_settings().gmail_send_enabled
                confirmed = st.checkbox(
                    "I reviewed the recipient and approve sending this email.",
                    key=f"confirm_send_{message.id}",
                    disabled=not allow_send,
                )
                if not allow_send:
                    st.caption(
                        "Live sending is disabled. Configure both Gmail opt-in "
                        "settings to enable it."
                    )
                if st.button(
                    "Send email",
                    key=f"send_{message.id}",
                    disabled=not (allow_send and confirmed),
                    type="primary",
                ):
                    try:
                        data.send_email(message.id)
                    except (
                        LookupError,
                        ValueError,
                        DuplicateOutreachError,
                        OutreachConfigurationError,
                        OutreachDeliveryError,
                        OutreachOutcomeUnknown,
                    ) as exc:
                        _show_error(exc)
                    else:
                        st.success("Email sent and logged.")
                        st.rerun()

            elif message.channel == "instagram_dm":
                if message.status == "approved":
                    st.info("Copy this DM and send it manually in Instagram.")
                    if st.button(
                        "Mark manually sent",
                        key=f"dm_sent_{message.id}",
                    ):
                        try:
                            data.mark_dm_sent(message.id)
                        except (
                            LookupError,
                            ValueError,
                            DuplicateOutreachError,
                        ) as exc:
                            _show_error(exc)
                        else:
                            st.success("Manual DM delivery recorded.")
                            st.rerun()
                elif message.status == "draft":
                    st.info(
                        "Approve this message on the Messages & review page "
                        "before sending it manually."
                    )

    st.subheader("Activity log")
    history = data.list_outreach_history()
    if history:
        st.dataframe(
            pd.DataFrame(history),
            use_container_width=True,
            hide_index=True,
        )
        st.download_button(
            "Download outreach CSV",
            data=pd.DataFrame(data.outreach_export_rows()).to_csv(
                index=False
            ).encode("utf-8"),
            file_name="outreach_history.csv",
            mime="text/csv",
        )
    else:
        st.info("No outreach activity has been logged yet.")


def main() -> None:
    data.initialize_database()
    st.title("Micro-Influencer Outreach")
    st.caption(
        "Discover creators, review personalized messages, and track outreach."
    )
    page = st.sidebar.radio(
        "Workspace",
        [
            "Discovery",
            "Influencers",
            "Messages & review",
            "Outreach tracker",
        ],
    )
    if page == "Discovery":
        _render_discovery()
    elif page == "Influencers":
        _render_influencers()
    elif page == "Messages & review":
        _render_messages()
    else:
        _render_outreach()


if __name__ == "__main__":
    main()
