import streamlit as st
import logging

LOGGER = logging.getLogger("startup")

# Python modules are cached in sys.modules and only run their top-level code once per server startup.
# Subsequent page refreshes/interactions will reuse the cached module and skip this block.
if "_started" not in globals():
    globals()["_started"] = True
    try:
        st.cache_data.clear()
        st.cache_resource.clear()
        LOGGER.info("🚀 Streamlit server startup: Caches cleared successfully.")
    except Exception as e:
        LOGGER.error("Failed to clear caches on startup: %s", e)
