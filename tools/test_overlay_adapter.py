from screenalert_core.rendering.overlay_adapter import OverlayAdapter
print('Creating adapter...')
ad = OverlayAdapter()
print('Adapter created, plugin:', ad.plugin is not None)
if ad.plugin:
    print('Plugin lists:', ad.plugin.list_overlays())
else:
    print('No plugin available')
