# PixelOn

[![en](https://img.shields.io/badge/lang-en-red.svg)](README.md)
[![kr](https://img.shields.io/badge/lang-kr-blue.svg)](./readme/README.kr.md)

## What is PixelOn?
![PixelOn Main](imgs/1.png)

**PixelOn** is an extension that adds **On-Device** image generation capabilities to **Piskel**, the PixelArt Editor.
This allows users to create pixel art using AI image generation easily and quickly, anywhere and anytime.

Boost your expressiveness!

We used Stable Diffusion C++ to implement lightweight and fast image generation. Combined with Piskel, it provides a seamless creative experience. Also, to enrich children's imagination, generated images can be utilized like a coloring book through the 'Export to Layer' feature.

This project was designed and developed to allow anyone to use Generative AI on their own computer as GPU adoption in households increases, moving away from cloud-based generators that require continuous subscription fees.

### Key Features
* **AI Image Generation:** Generate pixel art via text prompts
* **Compatibility:** Fully compatible with existing `.piskel` files
* **Export:** Immediately export generated images to Editor layers

### System Requirements (Minimum & Recommended)
| Type | Minimum | Recommended |
| :--- | :--- | :--- |
| **CPU** | Intel i5 or higher | Intel i5 or higher |
| **RAM** | 16GB or higher | 16GB or higher |
| **GPU** | NVIDIA RTX 2000 Series (4GB VRAM+) | NVIDIA RTX 3070 or higher |
| **Disk** | 20GB+ Free Space | 20GB+ Free Space |

> **Notice 1:** CPU-only usage is possible, but it may take 2-3 minutes or more per image. (Approx. 10s on RTX 2060)
> **Notice 2:** AMD GPU support will be updated in the future.

### Open Source Credits
* [Stable Diffusion C++](https://github.com/leejet/stable-diffusion.cpp)
* [Piskel](https://www.piskelapp.com/)
    * [PixelOn Piskel Repository](URL_HERE)
* **Stable Diffusion Models**
    * [LORA Model](URL_HERE)
    * Other utilized models

---

## How to install Piskel & PixelOn?
![PixelOn Installer](imgs/2.png)
1. Click **[Download PixelOn Installer](URL_HERE)** to get the installation file.
2. Run the installer to automatically scan your system and select the optimal acceleration version (CUDA, etc.).
3. Once installation is complete, run **PixelOn** from your desktop.

### Q & A
* **Q. I have an Nvidia GPU but CUDA is not selected.**
    * A. Your GPU driver might be outdated. Please update to the latest version at [Nvidia Driver Download](https://www.nvidia.com/Download/index.aspx).
* **Q. It says "Server Connection Failed".**
    * A. There may be missing files due to network issues during installation. Please reinstall via the installer.
* **Q. Generation speed is too slow.**
    * A. Speed can be slow if you don't have a GPU accelerator or meet the specs. This is a physical limitation of local execution.

---

## How to Use PixelOn?

### 1. Piskel Editor
When you run PixelOn, the Piskel editor screen appears. You can perform dot work just like existing Piskel usage. For detailed usage, please refer to the **[Piskel Official Guide](https://www.piskelapp.com/wiki/help)**.

### 2. Simple Prompt
![Simple Prompt UI](imgs/3.png)
You can quickly generate images using the prompt window at the bottom of the editor. Only **Positive Prompts** can be entered in this window.

### 3. Detail Dialog
![Detail Dialog UI](imgs/4.png)
Open the Detail window for more precise work. Detailed descriptions of each component are below.

<br>

<table>
<tr>
<td width="50%" valign="top">
    <img src="imgs/5.png" alt="History UI" style="max-width:100%;">
</td>
<td width="50%" valign="top">
    <h3>ⓐ History Management</h3>
    <p>Manage previous work sessions in the <b>History</b> tab.</p>
    <ul>
        <li><b>Click Session:</b> View past generation records.</li>
        <li><b>... Button:</b> Rename or delete the session.</li>
        <li><b>Warning:</b> Deletion cannot be undone (Undo), so please decide carefully.</li>
    </ul>
</td>
</tr>
</table>

<br>

<table>
<tr>
<td width="50%" valign="top">
    <img src="imgs/6.png" alt="Settings UI" style="max-width:100%;">
</td>
<td width="50%" valign="top">
    <h3>ⓑ Prompt & Settings</h3>
    <p>Manipulate key settings for image generation.</p>
    <ul>
        <li><b>Positive Prompt:</b> Scene description (Tag format, separated by Enter)</li>
        <li><b>Negative Prompt:</b> Elements to exclude (e.g., low quality)</li>
        <li><b>Preset:</b> Select model preset (Normal, Pixel Art, etc.)</li>
        <li><b>Resolution / Count:</b> Adjust image size and count</li>
    </ul>
    <blockquote><b>Note:</b> If the resolution is too small, the image may not generate correctly.</blockquote>
</td>
</tr>
</table>

<br>

<table>
<tr>
<td width="50%" valign="top">
    <img src="imgs/7.png" alt="Results UI" style="max-width:100%;">
</td>
<td width="50%" valign="top">
    <h3>ⓒ Results</h3>
    <p>Check and manage generated images.</p>
    <ul>
        <li><b>Left Click:</b> Select image</li>
        <li><b>... Click (Top of Image):</b>
            <ul>
                <li><i>Transfer:</i> Load settings from generation time</li>
                <li><i>Delete:</i> Delete the image</li>
            </ul>
        </li>
        <li><b>Cancel:</b> Deselect image</li>
        <li><b>Delete Selected:</b> Delete selected images in bulk</li>
    </ul>
    <blockquote><b>Warning:</b> Deletion cannot be undone.</blockquote>
</td>
</tr>
</table>

<br>

<table>
<tr>
<td width="50%" valign="top">
    <img src="imgs/8.png" alt="Log UI" style="max-width:100%;">
</td>
<td width="50%" valign="top">
    <h3>ⓓ Log, Expert</h3>
    <p>Check logs or send images to Editor.</p>
    <ul>
        <li><b>Move To Frame:</b> Exports selected images as <b>New Frames</b> respectively. (Useful for multi-image work)</li>
        <li><b>Move To Layer:</b> Exports the last selected image to the <b>Current Layer</b>. (Useful for single image work)</li>
    </ul>
</td>
</tr>
</table>

<br>

## Development Environment

### Prerequisites
* Windows OS
* Python >= 3.10
* Node.js
*(We build on Python 3.14 and Node 24.11.1)*

### How to setup
1. Prepare an environment that meets the above prerequisites.
2. Run `bootstrap.bat` to install necessary dependencies.
    * Includes: Stable Diffusion C++, Piskel (Forked Repo), AI Models
3. Run `python app.py` to start the local server.

### Contribute
Please use the `dev` branch if you want to contribute. Pull Requests are always welcome!

## License
This project follows the [MIT License](LICENSE).