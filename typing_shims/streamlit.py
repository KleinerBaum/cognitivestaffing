"""Typed shims for the subset of the Streamlit API used in the app."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = [
    "DeltaGenerator",
    "UploadedFile",
    "QueryParams",
    "session_state",
    "secrets",
    "query_params",
    "set_page_config",
    "cache_data",
    "button",
    "caption",
    "checkbox",
    "code",
    "color_picker",
    "columns",
    "container",
    "date_input",
    "divider",
    "download_button",
    "empty",
    "error",
    "expander",
    "experimental_rerun",
    "file_uploader",
    "form",
    "form_submit_button",
    "graphviz_chart",
    "header",
    "image",
    "info",
    "json",
    "markdown",
    "multiselect",
    "number_input",
    "plotly_chart",
    "radio",
    "rerun",
    "selectbox",
    "sidebar",
    "slider",
    "spinner",
    "subheader",
    "success",
    "tabs",
    "text_area",
    "text_input",
    "title",
    "toast",
    "toggle",
    "vega_lite_chart",
    "warning",
    "write",
]

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, MutableMapping, Sequence
    from contextlib import AbstractContextManager
    from datetime import date
    from types import TracebackType
    from typing import Any, Literal, ParamSpec, Protocol, TypeVar, overload, runtime_checkable

    _T = TypeVar("_T")
    _P = ParamSpec("_P")
    _Slider = TypeVar("_Slider", int, float)

    class CacheDataManager(Protocol):
        """Protocol describing ``st.cache_data`` along with its helpers."""

        def clear(self) -> None: ...

        def __call__(
            self,
            func: Callable[_P, _T] | None = ...,
            *,
            ttl: float | None = ...,
            show_spinner: bool = ...,
            max_entries: int | None = ...,
        ) -> Callable[_P, _T] | Callable[[Callable[_P, _T]], Callable[_P, _T]]: ...

    class QueryParams(Protocol):
        """Typed representation of ``st.query_params``."""

        def __getitem__(self, key: str) -> list[str]: ...

        def __setitem__(self, key: str, value: str | Sequence[str]) -> None: ...

        def __delitem__(self, key: str) -> None: ...

        def __iter__(self) -> Iterator[str]: ...

        def __len__(self) -> int: ...

        def get_all(self, key: str) -> list[str]: ...

    @runtime_checkable
    class UploadedFile(Protocol):
        """Subset of the ``UploadedFile`` interface used by the UI."""

        name: str
        type: str | None
        size: int

        def read(self, size: int | None = None) -> bytes: ...

        def seek(self, offset: int, whence: int = 0) -> int: ...

        def getvalue(self) -> bytes: ...

        def getbuffer(self) -> memoryview: ...

    class DeltaGenerator(Protocol):
        """Simplified ``DeltaGenerator`` protocol used across the wizard."""

        def __enter__(self) -> "DeltaGenerator": ...

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> bool | None: ...

        def button(
            self,
            label: str,
            *,
            key: str | None = None,
            help: str | None = None,
            type: Literal["primary", "secondary"] | str = "secondary",
            disabled: bool = False,
            use_container_width: bool = False,
            **widget_kwargs: Any,
        ) -> bool: ...

        def caption(self, body: str, *, help: str | None = None) -> "DeltaGenerator": ...

        def checkbox(
            self,
            label: str,
            *,
            value: bool = False,
            help: str | None = None,
            disabled: bool = False,
            key: str | None = None,
            **widget_kwargs: Any,
        ) -> bool: ...

        def code(self, body: str, language: str | None = None) -> "DeltaGenerator": ...

        def color_picker(
            self,
            label: str,
            *,
            value: str = "#000000",
            help: str | None = None,
            key: str | None = None,
            **widget_kwargs: Any,
        ) -> str: ...

        def columns(
            self,
            spec: Sequence[float | int] | int,
            *,
            gap: Literal["small", "medium", "large"] = "small",
        ) -> Sequence["DeltaGenerator"]: ...

        def container(self) -> "DeltaGenerator": ...

        def date_input(
            self,
            label: str,
            *,
            value: date | tuple[date, date] | None = None,
            min_value: date | None = None,
            max_value: date | None = None,
            help: str | None = None,
            key: str | None = None,
        ) -> date | tuple[date, date]: ...

        def divider(self) -> None: ...

        def download_button(
            self,
            label: str,
            data: str | bytes,
            *,
            file_name: str | None = None,
            mime: str | None = None,
            help: str | None = None,
            disabled: bool = False,
            type: Literal["primary", "secondary"] = "secondary",
            use_container_width: bool = False,
            key: str | None = None,
            **widget_kwargs: Any,
        ) -> bool: ...

        def empty(self) -> "DeltaGenerator": ...

        def error(self, body: str) -> "DeltaGenerator": ...

        def expander(
            self,
            label: str,
            *,
            expanded: bool = False,
            icon: str | None = None,
        ) -> "DeltaGenerator": ...

        def file_uploader(
            self,
            label: str,
            *,
            type: str | Sequence[str] | None = None,
            key: str | None = None,
            help: str | None = None,
            accept_multiple_files: bool = False,
            **widget_kwargs: Any,
        ) -> UploadedFile | None: ...

        def form(
            self,
            key: str,
            *,
            clear_on_submit: bool = False,
            border: bool = True,
        ) -> "DeltaGenerator": ...

        def form_submit_button(
            self,
            label: str,
            *,
            help: str | None = None,
            disabled: bool = False,
            type: Literal["primary", "secondary"] = "secondary",
            use_container_width: bool = False,
        ) -> bool: ...

        def graphviz_chart(
            self, figure_or_dot: object, *, use_container_width: bool | Literal["auto", "stretch"] = False
        ) -> None: ...

        def header(self, body: str, *, anchor: str | None = None) -> "DeltaGenerator": ...

        def image(
            self,
            image: object,
            *,
            caption: str | None = None,
            use_column_width: bool | Literal["auto"] | Literal["always"] | None = None,
            **widget_kwargs: Any,
        ) -> "DeltaGenerator": ...

        def info(self, body: str) -> "DeltaGenerator": ...

        def json(self, body: object) -> "DeltaGenerator": ...

        def markdown(
            self,
            body: str,
            *,
            unsafe_allow_html: bool = False,
            help: str | None = None,
        ) -> "DeltaGenerator": ...

        def multiselect(
            self,
            label: str,
            options: Sequence[_T],
            *,
            default: Sequence[_T] | None = None,
            help: str | None = None,
            key: str | None = None,
            **widget_kwargs: Any,
        ) -> list[_T]: ...

        def number_input(
            self,
            label: str,
            *,
            min_value: float | int | None = None,
            max_value: float | int | None = None,
            value: float | int | None = None,
            step: float | int | None = None,
            help: str | None = None,
            key: str | None = None,
        ) -> float | int: ...

        def plotly_chart(
            self,
            figure_or_data: object,
            *,
            use_container_width: bool | Literal["auto", "stretch"] = False,
            config: Mapping[str, object] | None = None,
            **widget_kwargs: Any,
        ) -> None: ...

        def radio(
            self,
            label: str,
            options: Sequence[_T],
            *,
            index: int = 0,
            help: str | None = None,
            key: str | None = None,
            **widget_kwargs: Any,
        ) -> _T: ...

        def selectbox(
            self,
            label: str,
            options: Sequence[_T],
            *,
            index: int = 0,
            help: str | None = None,
            key: str | None = None,
            **widget_kwargs: Any,
        ) -> _T: ...

        @overload
        def slider(
            self,
            label: str,
            *,
            min_value: _Slider | None = ...,
            max_value: _Slider | None = ...,
            value: tuple[_Slider, _Slider],
            step: _Slider | None = ...,
            help: str | None = ...,
            key: str | None = ...,
        ) -> tuple[_Slider, _Slider]: ...

        @overload
        def slider(
            self,
            label: str,
            *,
            min_value: _Slider | None = ...,
            max_value: _Slider | None = ...,
            value: _Slider | None = ...,
            step: _Slider | None = ...,
            help: str | None = ...,
            key: str | None = ...,
        ) -> _Slider: ...

        def slider(
            self,
            label: str,
            *,
            min_value: _Slider | None = ...,
            max_value: _Slider | None = ...,
            value: _Slider | tuple[_Slider, _Slider] | None = ...,
            step: _Slider | None = ...,
            help: str | None = ...,
            key: str | None = ...,
        ) -> _Slider | tuple[_Slider, _Slider]: ...

        def spinner(
            self,
            text: str = "In progress...",
        ) -> AbstractContextManager[None]: ...

        def subheader(self, body: str, *, anchor: str | None = None) -> "DeltaGenerator": ...

        def success(self, body: str) -> "DeltaGenerator": ...

        def tabs(
            self,
            tabs: Sequence[str],
            *,
            key: str | None = None,
        ) -> Sequence["DeltaGenerator"]: ...

        def text_area(
            self,
            label: str,
            *,
            value: str = "",
            height: int | None = None,
            help: str | None = None,
            key: str | None = None,
            **widget_kwargs: Any,
        ) -> str: ...

        def text_input(
            self,
            label: str,
            *,
            value: str = "",
            help: str | None = None,
            key: str | None = None,
            **widget_kwargs: Any,
        ) -> str: ...

        def title(self, body: str, *, anchor: str | None = None) -> "DeltaGenerator": ...

        def toggle(
            self,
            label: str,
            *,
            value: bool = False,
            help: str | None = None,
            key: str | None = None,
            **widget_kwargs: Any,
        ) -> bool: ...

        def vega_lite_chart(
            self,
            spec: Mapping[str, object] | Sequence[Mapping[str, object]],
            *,
            use_container_width: bool | Literal["auto", "stretch"] = False,
            width: int | Literal["auto", "stretch"] | None = None,
        ) -> None: ...

        def warning(self, body: str) -> "DeltaGenerator": ...

        def write(self, *args: object, **kwargs: object) -> None: ...

    session_state: MutableMapping[str, Any]
    secrets: Mapping[str, Any]
    query_params: QueryParams

    cache_data: CacheDataManager

    def set_page_config(
        *,
        page_title: str | None = None,
        page_icon: str | bytes | None = None,
        layout: Literal["centered", "wide"] = "centered",
        initial_sidebar_state: Literal["auto", "expanded", "collapsed"] = "auto",
    ) -> None: ...

    def button(
        label: str,
        *,
        key: str | None = None,
        help: str | None = None,
        type: Literal["primary", "secondary"] | str = "secondary",
        disabled: bool = False,
        use_container_width: bool = False,
        **widget_kwargs: Any,
    ) -> bool: ...

    def caption(body: str, *, help: str | None = None) -> DeltaGenerator: ...

    def checkbox(
        label: str,
        *,
        value: bool = False,
        help: str | None = None,
        disabled: bool = False,
        key: str | None = None,
        **widget_kwargs: Any,
    ) -> bool: ...

    def code(body: str, language: str | None = None) -> DeltaGenerator: ...

    def color_picker(
        label: str,
        *,
        value: str = "#000000",
        help: str | None = None,
        key: str | None = None,
        **widget_kwargs: Any,
    ) -> str: ...

    def columns(
        spec: Sequence[float | int] | int,
        *,
        gap: Literal["small", "medium", "large"] = "small",
    ) -> Sequence[DeltaGenerator]: ...

    def container() -> DeltaGenerator: ...

    def date_input(
        label: str,
        *,
        value: date | tuple[date, date] | None = None,
        min_value: date | None = None,
        max_value: date | None = None,
        help: str | None = None,
        key: str | None = None,
    ) -> date | tuple[date, date]: ...

    def divider() -> None: ...

    def download_button(
        label: str,
        data: str | bytes,
        *,
        file_name: str | None = None,
        mime: str | None = None,
        help: str | None = None,
        disabled: bool = False,
        type: Literal["primary", "secondary"] = "secondary",
        use_container_width: bool = False,
        key: str | None = None,
        **widget_kwargs: Any,
    ) -> bool: ...

    def empty() -> DeltaGenerator: ...

    def error(body: str) -> DeltaGenerator: ...

    def expander(
        label: str,
        *,
        expanded: bool = False,
        icon: str | None = None,
    ) -> DeltaGenerator: ...

    def experimental_rerun() -> None: ...

    def file_uploader(
        label: str,
        *,
        type: str | Sequence[str] | None = None,
        key: str | None = None,
        help: str | None = None,
        accept_multiple_files: bool = False,
        **widget_kwargs: Any,
    ) -> UploadedFile | None: ...

    def form(
        key: str,
        *,
        clear_on_submit: bool = False,
        border: bool = True,
    ) -> DeltaGenerator: ...

    def form_submit_button(
        label: str,
        *,
        help: str | None = None,
        disabled: bool = False,
        type: Literal["primary", "secondary"] = "secondary",
        use_container_width: bool = False,
    ) -> bool: ...

    def graphviz_chart(
        figure_or_dot: object,
        *,
        use_container_width: bool | Literal["auto", "stretch"] = False,
    ) -> None: ...

    def header(body: str, *, anchor: str | None = None) -> DeltaGenerator: ...

    def image(
        image: object,
        *,
        caption: str | None = None,
        use_column_width: bool | Literal["auto"] | Literal["always"] | None = None,
        **widget_kwargs: Any,
    ) -> DeltaGenerator: ...

    def info(body: str) -> DeltaGenerator: ...

    def json(body: object) -> DeltaGenerator: ...

    def markdown(
        body: str,
        *,
        unsafe_allow_html: bool = False,
        help: str | None = None,
    ) -> DeltaGenerator: ...

    def multiselect(
        label: str,
        options: Sequence[_T],
        *,
        default: Sequence[_T] | None = None,
        help: str | None = None,
        key: str | None = None,
        **widget_kwargs: Any,
    ) -> list[_T]: ...

    def number_input(
        label: str,
        *,
        min_value: float | int | None = None,
        max_value: float | int | None = None,
        value: float | int | None = None,
        step: float | int | None = None,
        help: str | None = None,
        key: str | None = None,
    ) -> float | int: ...

    def plotly_chart(
        figure_or_data: object,
        *,
        use_container_width: bool | Literal["auto", "stretch"] = False,
        config: Mapping[str, object] | None = None,
        **widget_kwargs: Any,
    ) -> None: ...

    def radio(
        label: str,
        options: Sequence[_T],
        *,
        index: int = 0,
        help: str | None = None,
        key: str | None = None,
        **widget_kwargs: Any,
    ) -> _T: ...

    def rerun() -> None: ...

    def selectbox(
        label: str,
        options: Sequence[_T],
        *,
        index: int = 0,
        help: str | None = None,
        key: str | None = None,
        **widget_kwargs: Any,
    ) -> _T: ...

    sidebar: DeltaGenerator

    @overload
    def slider(
        label: str,
        *,
        min_value: _Slider | None = ...,
        max_value: _Slider | None = ...,
        value: tuple[_Slider, _Slider],
        step: _Slider | None = ...,
        help: str | None = ...,
        key: str | None = ...,
    ) -> tuple[_Slider, _Slider]: ...

    @overload
    def slider(
        label: str,
        *,
        min_value: _Slider | None = ...,
        max_value: _Slider | None = ...,
        value: _Slider | None = ...,
        step: _Slider | None = ...,
        help: str | None = ...,
        key: str | None = ...,
    ) -> _Slider: ...

    def slider(
        label: str,
        *,
        min_value: _Slider | None = ...,
        max_value: _Slider | None = ...,
        value: _Slider | tuple[_Slider, _Slider] | None = ...,
        step: _Slider | None = ...,
        help: str | None = ...,
        key: str | None = ...,
    ) -> _Slider | tuple[_Slider, _Slider]: ...

    def spinner(text: str = "In progress...") -> AbstractContextManager[None]: ...

    def subheader(body: str, *, anchor: str | None = None) -> DeltaGenerator: ...

    def success(body: str) -> DeltaGenerator: ...

    def tabs(
        tabs: Sequence[str],
        *,
        key: str | None = None,
    ) -> Sequence[DeltaGenerator]: ...

    def text_area(
        label: str,
        *,
        value: str = "",
        height: int | None = None,
        help: str | None = None,
        key: str | None = None,
        **widget_kwargs: Any,
    ) -> str: ...

    def text_input(
        label: str,
        *,
        value: str = "",
        help: str | None = None,
        key: str | None = None,
        **widget_kwargs: Any,
    ) -> str: ...

    def title(body: str, *, anchor: str | None = None) -> DeltaGenerator: ...

    def toast(
        body: str,
        *,
        icon: str | None = None,
        duration: float | None = None,
    ) -> None: ...

    def toggle(
        label: str,
        *,
        value: bool = False,
        help: str | None = None,
        key: str | None = None,
        **widget_kwargs: Any,
    ) -> bool: ...

    def vega_lite_chart(
        spec: Mapping[str, object] | Sequence[Mapping[str, object]],
        *,
        use_container_width: bool | Literal["auto", "stretch"] = False,
        width: int | Literal["auto", "stretch"] | None = None,
    ) -> None: ...

    def warning(body: str) -> DeltaGenerator: ...

    def write(*args: object, **kwargs: object) -> None: ...
else:  # pragma: no cover - passthrough re-export
    import streamlit as _streamlit

    from streamlit.delta_generator import DeltaGenerator as DeltaGenerator
    from streamlit.runtime.uploaded_file_manager import (
        UploadedFile as UploadedFile,
    )

    session_state = _streamlit.session_state
    secrets = _streamlit.secrets
    query_params = _streamlit.query_params

    set_page_config = _streamlit.set_page_config
    cache_data = _streamlit.cache_data
    button = _streamlit.button
    caption = _streamlit.caption
    checkbox = _streamlit.checkbox
    code = _streamlit.code
    color_picker = _streamlit.color_picker
    columns = _streamlit.columns
    container = _streamlit.container
    date_input = _streamlit.date_input
    divider = _streamlit.divider
    download_button = _streamlit.download_button
    empty = _streamlit.empty
    error = _streamlit.error
    expander = _streamlit.expander
    experimental_rerun = getattr(_streamlit, "experimental_rerun", _streamlit.rerun)
    file_uploader = _streamlit.file_uploader
    form = _streamlit.form
    form_submit_button = _streamlit.form_submit_button
    graphviz_chart = _streamlit.graphviz_chart
    header = _streamlit.header
    image = _streamlit.image
    info = _streamlit.info
    json = _streamlit.json
    markdown = _streamlit.markdown
    multiselect = _streamlit.multiselect
    number_input = _streamlit.number_input
    plotly_chart = _streamlit.plotly_chart
    radio = _streamlit.radio
    rerun = _streamlit.rerun
    selectbox = _streamlit.selectbox
    sidebar = _streamlit.sidebar
    slider = _streamlit.slider
    spinner = _streamlit.spinner
    subheader = _streamlit.subheader
    success = _streamlit.success
    tabs = _streamlit.tabs
    text_area = _streamlit.text_area
    text_input = _streamlit.text_input
    title = _streamlit.title
    toast = _streamlit.toast
    toggle = _streamlit.toggle
    vega_lite_chart = _streamlit.vega_lite_chart
    warning = _streamlit.warning
    write = _streamlit.write
