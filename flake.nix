{
  description = "Provider-agnostic MCP server for ServiceDesk Plus on-premises";

  inputs = {
    nixpkgs.url = "https://flakehub.com/f/NixOS/nixpkgs/*";
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      treefmt-nix,
      ...
    }:
    let
      forAllSystems = nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed;
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python313;
        in
        rec {
          servicedesk-mcp-server = python.pkgs.buildPythonApplication {
            pname = "servicedesk-mcp-server";
            version = "2.0.0";
            pyproject = true;
            src = nixpkgs.lib.cleanSource ./.;

            build-system = [ python.pkgs.hatchling ];
            dependencies = with python.pkgs; [
              fastmcp
              httpx
              pydantic
            ];
            nativeCheckInputs = with python.pkgs; [ pytest ];
            pythonImportsCheck = [ "servicedesk_mcp" ];
            checkPhase = ''
              runHook preCheck
              pytest
              runHook postCheck
            '';

            meta = {
              description = "MCP server for ManageEngine ServiceDesk Plus on-premises";
              homepage = "https://github.com/dtvillafana/zoho-desk-mcp-server";
              license = pkgs.lib.licenses.gpl2Plus;
              mainProgram = "servicedesk-mcp-server";
            };
          };
          default = servicedesk-mcp-server;
        }
      );

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${nixpkgs.lib.getExe self.packages.${system}.default}";
        };
      });

      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python313.withPackages (
            ps: with ps; [
              fastmcp
              hatchling
              httpx
              pydantic
              pytest
              ruff
            ]
          );
        in
        {
          default = pkgs.mkShell {
            packages = [ python ];
            shellHook = ''
              export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
            '';
          };
        }
      );

      formatter = forAllSystems (
        system:
        treefmt-nix.lib.mkWrapper nixpkgs.legacyPackages.${system} {
          projectRootFile = "flake.nix";
          programs.nixfmt.enable = true;
          programs.ruff-format.enable = true;
        }
      );
    };
}
