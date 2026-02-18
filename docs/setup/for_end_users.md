# Install and Launch for End Users

At version 1.0, QuickView is expected to be installed and used from a personal
computer with the data files also being local. Future versions will support the
server-client model allowing access to remote data.

Releases so far have focused on macOS. Support for more systems will be added in
the near [future](../future.md).

---

# Install

For end users, pre-built binaries are available and can be installed with just a
few steps, as described below.

1. Download a pre-built binary from the
   [releases page](https://github.com/ayenpure/QuickView/releases/). macOS users
   with Apple Silicon chips should download a `*_aarch64.dmg`, and those with
   Intel chips should download a `*_x64.dmg` file.

2. **Important:** After the download, use the following command in Terminal to
   unblock the app for macOS:

   ```
   xattr -d com.apple.quarantine <your_filename>.dmg
   ```

   Explanation: In order to facilitate frequent iterations between our
   developers on the software and science sides, disk images are built and made
   public using GitHub's automated release process rather than being manually
   built and then signed at Kitware. Hence the `.dmg` files on the GitHub
   releases page have not been signed using an Apple Developer ID, and the
   command provided above is needed, so that after download, the macOS
   Gatekeeper will not block the app.

3. Double-click the downloaded `.dmg` file. In the pop-up window, drag the
   QuickView icon into the Applications folder.

!!! tip "Tip: No Worries about Dependencies"

    The pre-built binaries include the dependencies required to
    start the app locally. Any additional dependencies for data processing
    and visualization are downloaded and installed automatically on the first launch.

---

# Launch

To launch the EAM QuickView GUI, simply double-click the app icon in the
Applications folder.

!!! tip "Tip: Patience with the First Launch"

    On the first launch of a new app version, required dependencies are
    downloaded and installed. This may take a minute or more, depending
    on the Internet connection. Subsequent launches typically take only a few seconds.

---

# Within a conda environment

You can install `e3sm-quickview` directly in your conda environment via this
simple command `conda install -c conda-forge e3sm-quickview`. But you can also
create a new environment and install into it like below:

```
conda create --name e3sm-quickview python=3.13
conda activate e3sm-quickview
conda install -c conda-forge e3sm-quickview
```

Then when that conda environment is active, you can run the following command
line to start the application.

```
quickview
```

Common options are as follow:

- `--server` to prevent the browser to pop.
- `--port 1245` to choose a specific port number to be used locally. You can
  also use `0` as a way to let the system pick an available port automatically.
- `--host 0.0.0.0` to allow external connection on Linux.
- `--help` to list all the options.
