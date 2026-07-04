{
  description = "Development Shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    coding-utilities-src.url = "github:muralivnv/coding_utilities";
    ghostty-src = { url = "https://github.com/pkgforge-dev/ghostty-appimage/releases/download/v1.3.1/Ghostty-1.3.1-x86_64.AppImage"; flake = false; };
  };

  outputs = { self, nixpkgs, coding-utilities-src, ghostty-src, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      
      coding-utilities = coding-utilities-src.packages.${system}.default;

      ghostty = pkgs.stdenvNoCC.mkDerivation {
        pname = "ghostty";
        version = "1.3.1";
        src = ghostty-src;
        dontUnpack = true; 
        installPhase = ''
          mkdir -p $out/bin
          # Copy the raw AppImage directly to the bin folder
          cp $src $out/bin/ghostty
          chmod +x $out/bin/ghostty
        '';
      };

    in {
      devShells.${system}.default = pkgs.mkShellNoCC {

        buildInputs = with pkgs; [
          gitMinimal fzf bat zoxide starship pastel yazi-unwrapped tmux helix uv moreutils socat
          coding-utilities ghostty
        ];

        shellHook = ''
          source $PWD/bash_custom_functions.sh
          source $PWD/fzf-bash-completion.sh
          source $PWD/bash_config.sh
        '';
      };
    };

}   
