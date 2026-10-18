"""R3 — a shopping assistant that doesn't lie.   Launch:  streamlit run app.py"""
import streamlit as st

from r3.assistant import Session, fmt_price, fmt_rating, fmt_stock
from r3.factory import build_assistant

st.set_page_config(page_title="R3 Shopping Assistant", page_icon="🛍️", layout="wide")
st.markdown("""<style>
.block-container{max-width:1100px;padding-top:1.5rem}
.r3-badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.78rem;font-weight:600}
.in{background:#e6f4ea;color:#137333}.out{background:#fce8e6;color:#c5221f}.na{background:#eee;color:#555}
.r3-cite{font-size:.75rem;color:#666}
</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading catalogue and building the index (first run only)…")
def load():
    return build_assistant()


assistant = load()
if "session" not in st.session_state:
    st.session_state.session = Session()
    st.session_state.msgs = []          # [{role, text, products, meta}]
session: Session = st.session_state.session


def card(p):
    badge = {True: ("in", "In stock"), False: ("out", "Out of stock")}.get(p.stock, ("na", "Stock not listed"))
    with st.container(border=True):
        st.markdown(f"**{p.title}**  \n<span class='r3-cite'>ID {p.id} · {p.category or 'category not listed'}</span>",
                    unsafe_allow_html=True)
        st.markdown(f"### {fmt_price(p.price)}")
        st.markdown(f"<span class='r3-badge {badge[0]}'>{badge[1]}</span> &nbsp; {fmt_rating(p.rating)}",
                    unsafe_allow_html=True)
        if p.attributes:
            st.caption(" · ".join(f"{k}: {v}" for k, v in list(p.attributes.items())[:4]))
        st.markdown(f"<span class='r3-cite'>Source: catalogue entry [ID {p.id}]</span>", unsafe_allow_html=True)


def show(m):
    st.markdown(m["text"])
    if m.get("products"):
        cols = st.columns(len(m["products"]))
        for c, p in zip(cols, m["products"]):
            with c:
                card(p)
    if m.get("meta"):
        st.caption(m["meta"])



# 1) handle new input FIRST so the sidebar and history below already reflect it
if prompt := st.chat_input("e.g. cotton kurta under 1500, or: what is your return policy?"):
    st.session_state.msgs.append({"role": "user", "text": prompt})
    reply = assistant.chat(session, prompt)
    v = reply.validation
    meta = (f"{reply.outcome} · {reply.latency_ms:.0f} ms · "
            f"{'✅ validated against catalogue/policy' if v and v.ok else '⛔ blocked by validator'}"
            + (f" · filters: {reply.filters}" if reply.filters else ""))
    st.session_state.msgs.append({"role": "assistant", "text": reply.text, "products": reply.products, "meta": meta})

# 2) sidebar
with st.sidebar:
    st.title("🛍️ R3")
    st.caption("Answers only from the supplied catalogue and policy. If the evidence isn't there, it says so.")
    if assistant.is_mock:
        st.warning("**MOCK DATA** is loaded (no organiser files found in `data/`). "
                   "Copy the real catalogue and policy into `data/` and restart.")
    else:
        st.success("Using organiser catalogue + policy.")
    st.write(f"**{len(assistant.products):,}** products · embedder: `{assistant.embedder_name}`")
    st.subheader("What I'm remembering")
    st.write(session.describe() or "_nothing yet_")
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.session, st.session_state.msgs = Session(), []
        st.rerun()
    st.divider()
    st.caption("Try: “cotton shirts under ₹1500” → “only in stock” → “is the first one rated above 4?” · "
               "“how long do refunds take?” · “iPhone 17”")

# 3) conversation history
st.title("Ask about products, returns, shipping or warranty")
for m in st.session_state.msgs:
    with st.chat_message(m["role"]):
        show(m)
