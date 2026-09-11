{
  description = "Mimir-Win - 在 Linux 桌面上无缝运行 Windows 应用";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python3;
      in
      {
        packages = {
          mimir-win = python.pkgs.buildPythonPackage rec {
            pname = "mimir-win";
            version = "0.1.0";
            src = ./.;
            format = "pyproject";

            nativeBuildInputs = with python.pkgs; [
              hatchling
            ];

            propagatedBuildInputs = with python.pkgs; [
              tomli
            ];

            # 运行时依赖
            makeWrapperArgs = [
              "--prefix PATH : ${pkgs.lib.makeBinPath (with pkgs; [
                freerdp
                podman
                podman-compose
              ])}"
            ];

            postInstall = ''
              # 复制 Guest Agent 资产
              mkdir -p $out/share/mimir-win/guest
              cp -r ${./guest}/* $out/share/mimir-win/guest/

              # 复制 NixOS module
              mkdir -p $out/share/mimir-win/modules
              cp ${./modules/mimir-win.nix} $out/share/mimir-win/modules/mimir-win.nix
            '';

            meta = with pkgs.lib; {
              description = "在 Linux 桌面上无缝运行 Windows 应用";
              homepage = "https://github.com/user/mimir-win";
              license = licenses.mit;
              platforms = [ "x86_64-linux" ];
            };
          };

          default = self.packages.${system}.mimir-win;
        };

        # 开发环境
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python
            python.pkgs.tomli
            python.pkgs.pytest
            python.pkgs.ruff
            freerdp
            podman
            podman-compose
          ];

          shellHook = ''
            export MIMIR_WIN_DEV=1
            export PYTHONPATH="${./src}:$PYTHONPATH"
          '';
        };
      }
    ) // {
      # NixOS module - 三要素之一
      nixosModules.mimir-win = import ./modules/mimir-win.nix;
      nixosModules.default = self.nixosModules.mimir-win;
    };
}
