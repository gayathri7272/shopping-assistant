"""R3 — The Conversational Shopping Assistant That Doesn't Lie.
Launch:  streamlit run app.py
"""
import streamlit as st

from r3.assistant import Session, fmt_price, fmt_rating, fmt_stock
from r3.factory import build_assistant

st.set_page_config(
    page_title="R3 Shopping Assistant",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# Professional Navy / Blue Modern Theme & Styles
# -----------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #0f172a;
}

.block-container {
    max-width: 1180px;
    padding-top: 1.2rem;
    padding-bottom: 3rem;
}

/* Header Container */
.r3-header-card {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #1e3a8a 100%);
    border-radius: 16px;
    padding: 24px 30px;
    margin-bottom: 20px;
    color: #ffffff;
    box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.08);
}

.r3-header-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 12px;
}

.r3-brand-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(59, 130, 246, 0.25);
    border: 1px solid rgba(147, 197, 253, 0.35);
    color: #bfdbfe;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 4px 12px;
    border-radius: 20px;
    text-transform: uppercase;
}

.r3-trust-tags {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.r3-trust-tag {
    font-size: 0.75rem;
    background: rgba(255, 255, 255, 0.1);
    color: #e2e8f0;
    padding: 3px 10px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.15);
}

.r3-main-title {
    font-size: 2rem;
    font-weight: 800;
    color: #ffffff;
    margin: 0 0 4px 0;
    letter-spacing: -0.02em;
}

.r3-tagline {
    font-size: 1.05rem;
    color: #93c5fd;
    margin: 0;
    font-weight: 500;
}

/* Prompt Suggestions */
.r3-suggestions-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #475569;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* Product Cards */
.r3-product-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 16px;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
    transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}

.r3-product-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(37, 99, 235, 0.08);
    border-color: #93c5fd;
}

.r3-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 8px;
}

.r3-card-title {
    font-size: 1rem;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.35;
    margin: 0;
}

.r3-cite-tag {
    display: inline-block;
    background: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
    white-space: nowrap;
}

.r3-card-category {
    font-size: 0.78rem;
    color: #64748b;
    margin-bottom: 10px;
    font-weight: 500;
}

.r3-card-price {
    font-size: 1.35rem;
    font-weight: 800;
    color: #1e3a8a;
    margin: 6px 0 10px 0;
    letter-spacing: -0.01em;
}

.r3-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 12px;
}

.r3-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 9px;
    border-radius: 8px;
    font-size: 0.74rem;
    font-weight: 600;
}

.r3-pill-in {
    background: #ecfdf5;
    color: #065f46;
    border: 1px solid #a7f3d0;
}

.r3-pill-out {
    background: #fef2f2;
    color: #991b1b;
    border: 1px solid #fecaca;
}

.r3-pill-rating {
    background: #fffbeb;
    color: #92400e;
    border: 1px solid #fde68a;
}

.r3-attrs-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px dashed #e2e8f0;
}

.r3-attr-tag {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    color: #475569;
    font-size: 0.72rem;
    padding: 2px 6px;
    border-radius: 4px;
}

.r3-card-footer {
    margin-top: 12px;
    padding-top: 8px;
    border-top: 1px solid #f1f5f9;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.72rem;
    color: #64748b;
}

/* Callout Blocks for Refusals, Clarifications & Policy */
.r3-callout {
    padding: 14px 18px;
    border-radius: 12px;
    margin: 10px 0;
    font-size: 0.95rem;
    line-height: 1.5;
}

.r3-callout-clarify {
    background: #fffbeb;
    border: 1px solid #fde68a;
    color: #78350f;
}

.r3-callout-refusal {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    color: #334155;
}

.r3-callout-policy {
    background: #eff6ff;
    border-left: 4px solid #2563eb;
    border-top: 1px solid #dbeafe;
    border-right: 1px solid #dbeafe;
    border-bottom: 1px solid #dbeafe;
    color: #1e3a8a;
}

/* Meta badge under answers */
.r3-meta-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.74rem;
    color: #64748b;
    margin-top: 6px;
    padding: 4px 8px;
    background: #f8fafc;
    border-radius: 6px;
    width: fit-content;
    border: 1px solid #f1f5f9;
}

.r3-meta-ok {
    color: #166534;
    font-weight: 600;
}

.r3-meta-blocked {
    color: #991b1b;
    font-weight: 600;
}

/* Sidebar Styling */
.r3-sidebar-alert {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 10px;
    padding: 10px 14px;
    color: #9a3412;
    font-size: 0.8rem;
    line-height: 1.4;
    margin-bottom: 14px;
}

.r3-sidebar-success {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    border-radius: 10px;
    padding: 10px 14px;
    color: #065f46;
    font-size: 0.8rem;
    line-height: 1.4;
    margin-bottom: 14px;
}

.r3-filter-tag {
    display: inline-block;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1e40af;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    margin: 2px;
}
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Assistant Initialization
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Initializing catalogue index and validation pipeline…")
def load():
    return build_assistant()


assistant = load()

if "session" not in st.session_state:
    st.session_state.session = Session()
    st.session_state.msgs = []
session: Session = st.session_state.session


# -----------------------------------------------------------------------------
# Component: Product Result Card
# -----------------------------------------------------------------------------
def render_product_card(p):
    """Renders a product card displaying attributes only when present in catalogue."""
    with st.container():
        st.markdown(f"""
        <div class="r3-product-card">
            <div>
                <div class="r3-card-header">
                    <h4 class="r3-card-title">{p.title}</h4>
                    <span class="r3-cite-tag" title="Catalogue Citation ID">ID {p.id}</span>
                </div>
                <div class="r3-card-category">
                    {f"📁 {p.category}" if p.category else "Category not listed"}
                </div>
                {f'<div class="r3-card-price">{fmt_price(p.price)}</div>' if p.price is not None else '<div class="r3-card-price" style="font-size:0.95rem;color:#64748b;">Price not listed</div>'}
                <div class="r3-badge-row">
                    {f'<span class="r3-pill r3-pill-in">✓ In stock</span>' if p.stock is True else (f'<span class="r3-pill r3-pill-out">✕ Out of stock</span>' if p.stock is False else '')}
                    {f'<span class="r3-pill r3-pill-rating">★ {p.rating:.1f}</span>' if p.rating is not None else ''}
                </div>
                {f'<div class="r3-attrs-row">{"".join(f"""<span class="r3-attr-tag"><b>{k}:</b> {v}</span>""" for k, v in list(p.attributes.items())[:4])}</div>' if p.attributes else ''}
            </div>
            <div class="r3-card-footer">
                <span>🛡️ Catalogue verified</span>
                <span style="font-weight:600;color:#2563eb;">[ID {p.id}]</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Component: Assistant Message Formatter
# -----------------------------------------------------------------------------
def render_message(m):
    role = m["role"]
    text = m["text"]
    outcome = m.get("outcome", "")
    products = m.get("products", [])
    meta = m.get("meta", "")

    if role == "user":
        st.markdown(f"**You:** {text}")
        return

    # Visual callouts based on outcome
    if outcome == "clarify":
        st.markdown(f"""<div class="r3-callout r3-callout-clarify">🤔 <b>Narrow Your Search:</b><br>{text}</div>""", unsafe_allow_html=True)
    elif outcome in ("not_found", "policy_refusal", "no_match"):
        st.markdown(f"""<div class="r3-callout r3-callout-refusal">🛡️ <b>Grounded Refusal:</b><br>{text}</div>""", unsafe_allow_html=True)
    elif outcome == "policy":
        st.markdown(f"""<div class="r3-callout r3-callout-policy">📜 <b>Official Store Policy Citation:</b><br>{text}</div>""", unsafe_allow_html=True)
    elif outcome == "blocked":
        st.markdown(f"""<div class="r3-callout" style="background:#fef2f2;border:1px solid #fecaca;color:#991b1b;">⛔ <b>Safety Guard Interception:</b><br>{text}</div>""", unsafe_allow_html=True)
    else:
        st.markdown(text)

    # Render product cards in responsive grid
    if products:
        cols = st.columns(min(len(products), 3))
        for col, p in zip(cols, products):
            with col:
                render_product_card(p)

    if meta:
        st.markdown(f"""<div class="r3-meta-bar">{meta}</div>""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Input Handling & Execution
# -----------------------------------------------------------------------------
# Handle prompt from chat input or clicked suggestion buttons
prompt_from_input = st.chat_input("Ask about products, budget, specs, returns, or warranty...")
active_prompt = prompt_from_input or st.session_state.pop("pending_prompt", None)

if active_prompt:
    st.session_state.msgs.append({"role": "user", "text": active_prompt})
    reply = assistant.chat(session, active_prompt)
    v = reply.validation
    status_icon = "✅ Verified" if (v and v.ok) else "⛔ Blocked"
    status_class = "r3-meta-ok" if (v and v.ok) else "r3-meta-blocked"
    meta_text = (
        f"""<span class="{status_class}">{status_icon}</span> · """
        f"""<span>Outcome: <b>{reply.outcome}</b></span> · """
        f"""<span>⚡ {reply.latency_ms:.0f} ms</span> · """
        f"""<span>0 LLM Tokens ($0.00)</span>"""
        + (f""" · <span title="Active Session Filters">Filters: {reply.filters}</span>""" if reply.filters else "")
    )
    st.session_state.msgs.append({
        "role": "assistant",
        "text": reply.text,
        "products": reply.products,
        "outcome": reply.outcome,
        "meta": meta_text
    })


# -----------------------------------------------------------------------------
# Header Presentation
# -----------------------------------------------------------------------------
st.markdown("""
<div class="r3-header-card">
    <div class="r3-header-top">
        <div class="r3-brand-pill">🛍️ R3 Engine v1.0</div>
        <div class="r3-trust-tags">
            <span class="r3-trust-tag">🛡️ Zero Hallucination Guarantee</span>
            <span class="r3-trust-tag">📋 Deterministic Citations</span>
            <span class="r3-trust-tag">⚡ Offline Sub-30ms Retrieval</span>
        </div>
    </div>
    <h1 class="r3-main-title">R3 Shopping Assistant</h1>
    <p class="r3-tagline">Discover products. Trust every answer.</p>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Suggested Shopping Prompts (Quick Click Actions)
# -----------------------------------------------------------------------------
st.markdown('<div class="r3-suggestions-title">💡 <b>Quick shopping queries (Click to test):</b></div>', unsafe_allow_html=True)
sug_cols = st.columns(5)
suggestions = [
    ("👔 Cotton shirts < ₹1500", "cotton shirts under 1500"),
    ("👟 Top rated running shoes", "top rated running shoes"),
    ("🎧 Headphones in stock", "wireless headphones in stock"),
    ("📦 Return policy", "how many days do I have to return an item?"),
    ("🔍 iPhone 17 (Unknown test)", "iPhone 17 Pro Max"),
]

for col, (label, query) in zip(sug_cols, suggestions):
    with col:
        if st.button(label, key=f"btn_{label}", use_container_width=True):
            st.session_state.pending_prompt = query
            st.rerun()


# -----------------------------------------------------------------------------
# Sidebar: Controls, Memory & Catalogue Status
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🛍️ R3 Assistant")
    st.caption("Answers strictly verified against catalogue entries & store policies.")

    if assistant.is_mock:
        st.markdown("""
        <div class="r3-sidebar-alert">
            <b>⚠️ MOCK DATA ACTIVE</b><br>
            200 synthetic items loaded. Organiser files (catalogue, policy, test questions) not yet placed in <code>data/</code>.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="r3-sidebar-success">
            <b>✅ ORGANISER DATA ACTIVE</b><br>
            Verified against official catalogue and store policies.
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"**Index:** `{len(assistant.products):,}` products  \n**Embedder:** `{assistant.embedder_name}`")
    st.divider()

    st.markdown("#### 🧠 Multi-Turn Memory")
    active_filters_desc = session.describe()
    if active_filters_desc:
        for f in active_filters_desc.split(" · "):
            st.markdown(f'<span class="r3-filter-tag">{f}</span>', unsafe_allow_html=True)
    else:
        st.caption("_No active constraints. Search to begin accumulating preferences._")

    st.write("")
    if st.button("🗑️ Clear conversation & filters", use_container_width=True, type="secondary"):
        st.session_state.session = Session()
        st.session_state.msgs = []
        st.rerun()

    st.divider()
    with st.expander("📖 Hackathon Demo Flow", expanded=False):
        st.markdown("""
        1. **Query:** `cotton clothes` → Asks clarifying question.
        2. **Filter:** `under 2000` → Returns verified cards with prices & `[ID MOCK-...]`.
        3. **Context:** `is the first one in stock?` → Resolves ordinal, cites fact.
        4. **Memory:** `forget the budget` → Drops budget, keeps cotton.
        5. **Refusal:** `iPhone 17 Pro Max` → Honest refusal without guessing.
        6. **Policy:** `how many days to return?` → Verifiable quote citation.
        """)


# -----------------------------------------------------------------------------
# Conversation History
# -----------------------------------------------------------------------------
st.write("")
if not st.session_state.msgs:
    st.info("👋 **Welcome to R3!** Start typing above or click any of the suggested queries to explore products or store policies with 100% verified answers.")
else:
    for m in st.session_state.msgs:
        with st.chat_message(m["role"]):
            render_message(m)
