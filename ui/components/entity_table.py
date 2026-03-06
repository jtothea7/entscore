"""
Entity gap comparison table
"""
import streamlit as st
import pandas as pd


def render_entity_table(entities: list, show_all: bool = False):
    """
    Render the entity gap comparison table.

    By default shows only missing and weak entities.
    Use show_all=True to show all entities including strong.
    """
    if not entities:
        st.info("No entity data available.")
        return

    # Filter based on view mode
    if not show_all:
        display_entities = [
            e for e in entities if e.get("gap_status") in ("missing", "weak")
        ]
    else:
        display_entities = entities

    if not display_entities:
        st.success("All important entities are covered on your page!")
        return

    # Build dataframe
    rows = []
    for ent in display_entities:
        status = ent.get("gap_status", "unknown")
        badge_class = f"badge-{status}"

        rows.append({
            "Entity": ent.get("entity_text", ""),
            "Type": ent.get("entity_type", "-"),
            "Status": status.title(),
            "Your Count": ent.get("client_count", 0),
            "Your Salience": f"{ent.get('client_salience', 0):.2f}",
            "Competitor Freq": f"{ent.get('competitor_frequency', 0)}/10",
            "Comp Avg Salience": f"{ent.get('competitor_avg_salience', 0):.2f}",
        })

    df = pd.DataFrame(rows)

    # Style the dataframe
    def color_status(val):
        colors = {
            "Missing": "background-color: #FEE2E2; color: #991B1B;",
            "Weak": "background-color: #FEF3C7; color: #92400E;",
            "Strong": "background-color: #D1FAE5; color: #065F46;",
        }
        return colors.get(val, "")

    styled_df = df.style.applymap(color_status, subset=["Status"])

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=min(400, len(rows) * 40 + 40),
    )

    # Summary counts
    missing = len([e for e in entities if e.get("gap_status") == "missing"])
    weak = len([e for e in entities if e.get("gap_status") == "weak"])
    strong = len([e for e in entities if e.get("gap_status") == "strong"])

    cols = st.columns(3)
    cols[0].metric("Missing", missing)
    cols[1].metric("Weak", weak)
    cols[2].metric("Strong", strong)
