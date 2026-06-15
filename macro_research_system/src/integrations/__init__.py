__all__ = [
    "build_macro_system_summary",
    "load_oil_rate_summary",
    "load_tw_margin_summary",
]


def __getattr__(name: str):
    if name == "build_macro_system_summary":
        from .macro_system_aggregator import build_macro_system_summary

        return build_macro_system_summary
    if name == "load_oil_rate_summary":
        from .oil_rate_adapter import load_oil_rate_summary

        return load_oil_rate_summary
    if name == "load_tw_margin_summary":
        from .tw_margin_adapter import load_tw_margin_summary

        return load_tw_margin_summary
    raise AttributeError(name)
