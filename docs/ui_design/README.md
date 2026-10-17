# Alora – wireframes and visual design (for Figma)

The same designs as the online canvas, as files you can put into Figma.

| Folder | What is inside |
|---|---|
| `png/00_user_flow.png` – `png/09_*.png` | User flow and low-fidelity wireframes (desktop 1280 px and phone 390 px), rendered at 2× |
| `png/10_style_guide.png` | Style guide: colours (light and dark), type scale, spacing, components |
| `png/screen_*.png` | Real Alora screens (light, dark, phone) |
| `html/*.html` | The wireframes and style guide as plain web pages. Use these to get **editable** Figma layers. |

## Option 1 – images (quickest; not editable)

1. Open Figma and create a new design file.
2. Drag the PNG files from `docs/ui_design/png/` onto the canvas, or press **Ctrl + Shift + K** to place them.
3. In the right panel, set each image to **50%** size. The images are rendered at 2× for sharpness, so 50% gives the real size, for example 1280 px wide.

## Option 2 – editable layers (text, boxes and colours you can change)

Use the free Figma plugin **html.to.design** (by ‹div›RIOTS). The free plan has a limited number of imports per month, so import only the screens you need.

1. In Figma, open **Plugins → Find more plugins**, search for **html.to.design**, and run it.
2. Install its **Chrome extension** too: the plugin links to it. Local files on your laptop can only be imported through the extension.
3. In Chrome, open a file from `docs/ui_design/html/`, for example `01_wireframe_home.html`. Set the window to the screen's width: 1280 px for desktop, 390 px for phone.
4. Click the html.to.design extension and choose to import the page. It downloads an import file.
5. Back in Figma, open the plugin and import that file. The screen appears as frames, text and shapes.

**Real app screens as editable layers:**
1. Start the app (`uvicorn backend.app:app --port 8000`).
2. Open a page in Chrome, for example `localhost:8000/?demo=average#/target`.
3. Import it with the extension in the same way.

## Option 3 – the online canvas

The canvas has the same designs: zoom, click-through wireframes, and export to PNG or PDF from its Share menu. You can't open it directly in Figma, but its PNG or PDF exports can be dragged into Figma like Option 1.
