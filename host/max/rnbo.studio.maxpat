{
  "patcher": {
    "fileversion": 1,
    "appversion": {
      "major": 9,
      "minor": 1,
      "revision": 4,
      "architecture": "arm64",
      "modernui": 1
    },
    "classnamespace": "box",
    "rect": [
      120,
      100,
      940,
      460
    ],
    "boxes": [
      {
        "box": {
          "id": "in",
          "maxclass": "inlet",
          "text": "",
          "patching_rect": [
            20,
            20,
            30,
            24
          ],
          "varname": "in"
        }
      },
      {
        "box": {
          "id": "caption",
          "maxclass": "comment",
          "text": "Build the live RNBO patch. Connect its dump outlet to this helper inlet.",
          "patching_rect": [
            70,
            20,
            700,
            24
          ],
          "varname": "caption"
        }
      },
      {
        "box": {
          "id": "build",
          "maxclass": "message",
          "text": "build",
          "patching_rect": [
            20,
            70,
            70,
            24
          ],
          "presentation": 1,
          "presentation_rect": [
            15,
            15,
            65,
            25
          ],
          "varname": "build"
        }
      },
      {
        "box": {
          "id": "build-label",
          "maxclass": "comment",
          "text": "Build for ESP32",
          "patching_rect": [
            110,
            70,
            200,
            24
          ],
          "presentation": 1,
          "presentation_rect": [
            95,
            15,
            190,
            25
          ],
          "varname": "build-label"
        }
      },
      {
        "box": {
          "id": "open",
          "maxclass": "message",
          "text": "open",
          "patching_rect": [
            20,
            110,
            70,
            24
          ],
          "presentation": 1,
          "presentation_rect": [
            15,
            55,
            65,
            25
          ],
          "varname": "open"
        }
      },
      {
        "box": {
          "id": "open-label",
          "maxclass": "comment",
          "text": "Open this build in Studio",
          "patching_rect": [
            110,
            110,
            260,
            24
          ],
          "presentation": 1,
          "presentation_rect": [
            95,
            55,
            210,
            25
          ],
          "varname": "open-label"
        }
      },
      {
        "box": {
          "id": "v8",
          "maxclass": "newobj",
          "text": "v8 rnbo-studio.js #1",
          "patching_rect": [
            20,
            175,
            420,
            24
          ],
          "varname": "v8"
        }
      },
      {
        "box": {
          "id": "node",
          "maxclass": "newobj",
          "text": "node.script rnbo-studio-client.js @autostart 1",
          "patching_rect": [
            20,
            240,
            600,
            24
          ],
          "varname": "node"
        }
      },
      {
        "box": {
          "id": "out",
          "maxclass": "outlet",
          "text": "",
          "patching_rect": [
            20,
            320,
            30,
            24
          ],
          "varname": "out"
        }
      },
      {
        "box": {
          "id": "print",
          "maxclass": "newobj",
          "text": "print RNBO_STUDIO",
          "patching_rect": [
            100,
            320,
            250,
            24
          ],
          "varname": "print"
        }
      },
      {
        "box": {
          "id": "browser",
          "maxclass": "message",
          "text": "; max launchbrowser $1",
          "patching_rect": [
            520,
            175,
            340,
            24
          ],
          "varname": "browser"
        }
      },
      {
        "box": {
          "id": "note",
          "maxclass": "comment",
          "text": "build compiles only. upload usb/wifi loads the last successful package. build_upload usb/wifi does both.",
          "patching_rect": [
            20,
            370,
            700,
            24
          ],
          "varname": "note"
        }
      },
      {
        "box": {
          "id": "status-label",
          "varname": "status_label",
          "maxclass": "comment",
          "text": "Starting build helper\u2026",
          "patching_rect": [
            20,
            410,
            800,
            40
          ],
          "presentation": 1,
          "presentation_rect": [
            15,
            135,
            335,
            55
          ]
        }
      },
      {
        "box": {
          "id": "upload-0",
          "maxclass": "message",
          "text": "upload usb",
          "patching_rect": [
            520,
            240,
            140,
            24
          ],
          "presentation": 1,
          "presentation_rect": [
            15,
            95,
            105,
            25
          ]
        }
      },
      {
        "box": {
          "id": "upload-1",
          "maxclass": "message",
          "text": "upload wifi",
          "patching_rect": [
            680,
            240,
            140,
            24
          ],
          "presentation": 1,
          "presentation_rect": [
            130,
            95,
            105,
            25
          ]
        }
      },
      {
        "box": {
          "id": "status-set",
          "maxclass": "newobj",
          "text": "prepend set",
          "patching_rect": [
            520,
            320,
            140,
            24
          ]
        }
      }
    ],
    "lines": [
      {
        "patchline": {
          "source": [
            "in",
            0
          ],
          "destination": [
            "v8",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "build",
            0
          ],
          "destination": [
            "v8",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "open",
            0
          ],
          "destination": [
            "v8",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "v8",
            0
          ],
          "destination": [
            "node",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "node",
            0
          ],
          "destination": [
            "v8",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "v8",
            1
          ],
          "destination": [
            "out",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "v8",
            1
          ],
          "destination": [
            "print",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "v8",
            2
          ],
          "destination": [
            "browser",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "upload-0",
            0
          ],
          "destination": [
            "v8",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "upload-1",
            0
          ],
          "destination": [
            "v8",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "v8",
            3
          ],
          "destination": [
            "status-set",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "status-set",
            0
          ],
          "destination": [
            "status-label",
            0
          ]
        }
      }
    ],
    "openinpresentation": 1
  }
}
