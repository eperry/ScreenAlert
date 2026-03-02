from screenalert_core.utils.plugin_hooks import PluginHooks


def test_register_emit_unregister():
    hooks = PluginHooks()
    calls = []

    def handler(value=None):
        calls.append(value)

    hooks.register("event.a", handler)
    hooks.emit("event.a", value=1)
    hooks.emit("event.a", value=2)

    assert calls == [1, 2]
    assert hooks.unregister("event.a", handler) is True
    hooks.emit("event.a", value=3)
    assert calls == [1, 2]


def test_list_and_clear_events():
    hooks = PluginHooks()

    hooks.register("b", lambda: None)
    hooks.register("a", lambda: None)

    assert hooks.list_events() == ["a", "b"]

    hooks.clear("a")
    assert hooks.list_events() == ["b"]

    hooks.clear()
    assert hooks.list_events() == []
