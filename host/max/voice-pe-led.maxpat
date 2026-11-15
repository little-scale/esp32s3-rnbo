{
  "patcher": {
    "fileversion": 1,
    "classnamespace": "box",
    "rect": [
      50,
      50,
      1100,
      650
    ],
    "boxes": [
      {
        "box": {
          "id": "heading",
          "maxclass": "comment",
          "text": "Voice PE LEDs: use native16 for the connected unit. Studio test parameter: 0 red, 1 LED3 green, 2 LED11 blue, 3 RGB36, 4/5/6 invalid, 7 clamp, 8 black, 9 blue.",
          "patching_rect": [
            30,
            30,
            650,
            22
          ]
        }
      },
      {
        "box": {
          "id": "native16",
          "maxclass": "message",
          "text": "profile voice-pe-16000-256-v1",
          "patching_rect": [
            30,
            75,
            650,
            22
          ]
        }
      },
      {
        "box": {
          "id": "native48",
          "maxclass": "message",
          "text": "profile voice-pe-48000-256-v1",
          "patching_rect": [
            30,
            110,
            650,
            22
          ]
        }
      },
      {
        "box": {
          "id": "build",
          "maxclass": "message",
          "text": "build",
          "patching_rect": [
            30,
            150,
            650,
            22
          ]
        }
      },
      {
        "box": {
          "id": "upload",
          "maxclass": "message",
          "text": "upload usb",
          "patching_rect": [
            30,
            185,
            650,
            22
          ]
        }
      },
      {
        "box": {
          "id": "helper",
          "maxclass": "newobj",
          "text": "rnbo.studio instrument",
          "patching_rect": [
            30,
            230,
            650,
            22
          ]
        }
      },
      {
        "box": {
          "id": "rnbo",
          "maxclass": "newobj",
          "text": "rnbo~ @title VoicePELED @dumpoutlet 1",
          "patching_rect": [
            30,
            280,
            650,
            22
          ],
          "patcher": {
            "fileversion": 1,
            "classnamespace": "rnbo",
            "rect": [
              100,
              100,
              1100,
              600
            ],
            "boxes": [
              {
                "box": {
                  "id": "obj-1",
                  "maxclass": "newobj",
                  "text": "param test 0 @min 0 @max 9 @steps 10",
                  "patching_rect": [
                    30,
                    30,
                    480,
                    22
                  ],
                  "rnbo_classname": "param",
                  "rnbo_uniqueid": "param_obj-1",
                  "rnbo_serial": 0,
                  "rnboinfo": {
                    "needsInstanceInfo": true,
                    "argnames": {
                      "value": {
                        "attrOrProp": 2,
                        "digest": "Set initial value",
                        "defaultarg": 2,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "number",
                        "defaultValue": "0",
                        "label": "Initial Value",
                        "displayorder": 3
                      },
                      "normalizedvalue": {
                        "attrOrProp": 1,
                        "digest": "Set value normalized. ",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number"
                      },
                      "reset": {
                        "attrOrProp": 1,
                        "digest": "Reset param to initial value",
                        "isalias": false,
                        "aliases": [],
                        "attachable": true,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bang"
                      },
                      "normalized": {
                        "attrOrProp": 1,
                        "digest": "Normalized parameter value.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "number"
                      },
                      "name": {
                        "attrOrProp": 2,
                        "digest": "Name of the parameter",
                        "defaultarg": 1,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "label": "Parameter Name",
                        "mandatory": true
                      },
                      "enum": {
                        "attrOrProp": 2,
                        "digest": "Use an enumerated output",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "label": "Enum Values",
                        "displayorder": 6
                      },
                      "minimum": {
                        "attrOrProp": 2,
                        "digest": "Minimum value",
                        "isalias": false,
                        "aliases": [
                          "min"
                        ],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "number",
                        "defaultValue": "0",
                        "label": "Minimum",
                        "displayorder": 1
                      },
                      "min": {
                        "attrOrProp": 2,
                        "digest": "Minimum value",
                        "isalias": true,
                        "aliasOf": "minimum",
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "number",
                        "defaultValue": "0",
                        "label": "Minimum",
                        "displayorder": 1
                      },
                      "maximum": {
                        "attrOrProp": 2,
                        "digest": "Maximum value",
                        "isalias": false,
                        "aliases": [
                          "max"
                        ],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "number",
                        "defaultValue": "1",
                        "label": "Maximum",
                        "displayorder": 2
                      },
                      "max": {
                        "attrOrProp": 2,
                        "digest": "Maximum value",
                        "isalias": true,
                        "aliasOf": "maximum",
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "number",
                        "defaultValue": "1",
                        "label": "Maximum",
                        "displayorder": 2
                      },
                      "exponent": {
                        "attrOrProp": 2,
                        "digest": "Scale values exponentially",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "number",
                        "defaultValue": "1",
                        "label": "Exponent",
                        "displayorder": 7
                      },
                      "steps": {
                        "attrOrProp": 2,
                        "digest": "Divide the output into a number of discrete steps",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "number",
                        "defaultValue": "0",
                        "label": "Steps",
                        "displayorder": 8
                      },
                      "displayName": {
                        "attrOrProp": 2,
                        "digest": "DEPRECATED: Use the lower case 'displayname' instead",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": true,
                        "touched": false,
                        "type": "symbol",
                        "label": "Display Name"
                      },
                      "displayname": {
                        "attrOrProp": 2,
                        "digest": "A more readable name for the parameter in an external RNBO target",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "defaultValue": "",
                        "label": "Display Name",
                        "displayorder": 14
                      },
                      "unit": {
                        "attrOrProp": 2,
                        "digest": "A symbol to describe the unit of the parameter in an external RNBO target",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "defaultValue": "",
                        "label": "Unit",
                        "displayorder": 15
                      },
                      "tonormalized": {
                        "attrOrProp": 2,
                        "digest": "Converts a real parameter value to its normalized form",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "label": "To Normalized Expression",
                        "displayorder": 10
                      },
                      "fromnormalized": {
                        "attrOrProp": 2,
                        "digest": "Converts a normalized parameter into its actual parameter value",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "label": "From Normalized Expression",
                        "displayorder": 9
                      },
                      "order": {
                        "attrOrProp": 2,
                        "digest": "Order in which initial parameter values will be sent out on patcher load. The order can be numeric or symbolic ('first' and 'last')",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "defaultValue": "0",
                        "label": "Restore Order",
                        "displayorder": 12
                      },
                      "displayorder": {
                        "attrOrProp": 2,
                        "digest": "Order in which parameters will show up in a list of all parameters. The order can be numeric or symbolic ('first' and 'last')",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "defaultValue": "-",
                        "label": "Display Order",
                        "displayorder": 13
                      },
                      "sendinit": {
                        "attrOrProp": 2,
                        "digest": "Send initial value",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "true",
                        "label": "Send Init",
                        "displayorder": 4
                      },
                      "ctlin": {
                        "attrOrProp": 2,
                        "digest": "MIDI controller number to control this parameter.",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "number",
                        "defaultValue": "-1",
                        "label": "MIDI Controller Number.",
                        "displayorder": 16
                      },
                      "meta": {
                        "attrOrProp": 2,
                        "digest": "A JSON formatted string containing metadata for use by the exported code",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "defaultValue": "",
                        "label": "Metadata",
                        "displayorder": 17
                      },
                      "nopreset": {
                        "attrOrProp": 2,
                        "digest": "Do not add this value to the preset [DEPRECATED - USE @preset 0 instead].",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": true,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false"
                      },
                      "preset": {
                        "attrOrProp": 2,
                        "digest": "Add this value to the preset.",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "true",
                        "label": "Include In Preset",
                        "displayorder": 11
                      }
                    },
                    "inputs": [
                      {
                        "name": "value",
                        "type": "number",
                        "digest": "Parameter value",
                        "defaultarg": 2,
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "normalizedvalue",
                        "type": "number",
                        "digest": "Set value normalized. ",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "value",
                        "type": "number",
                        "digest": "Parameter value",
                        "defaultarg": 2,
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "normalized",
                        "type": "number",
                        "digest": "Normalized parameter value.",
                        "docked": false
                      }
                    ],
                    "helpname": "param",
                    "aliasOf": "param",
                    "classname": "param",
                    "operator": false,
                    "versionId": -1093178486,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 2,
                  "outlettype": [
                    "",
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-2",
                  "maxclass": "newobj",
                  "text": "sel 0 1 2 3 4 5 6 7 8 9",
                  "patching_rect": [
                    30,
                    75,
                    480,
                    22
                  ],
                  "rnbo_classname": "sel",
                  "rnbo_uniqueid": "sel_obj-2",
                  "rnbo_serial": 1,
                  "rnboinfo": {
                    "needsInstanceInfo": true,
                    "argnames": {
                      "input": {
                        "attrOrProp": 1,
                        "digest": "Number to test",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number"
                      },
                      "test1": {
                        "attrOrProp": 1,
                        "digest": "Set Value (1) to Match",
                        "defaultarg": 1,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "0"
                      },
                      "test2": {
                        "attrOrProp": 1,
                        "digest": "Set Value (2) to Match",
                        "defaultarg": 2,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "1"
                      },
                      "test3": {
                        "attrOrProp": 1,
                        "digest": "Set Value (3) to Match",
                        "defaultarg": 3,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "2"
                      },
                      "test4": {
                        "attrOrProp": 1,
                        "digest": "Set Value (4) to Match",
                        "defaultarg": 4,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "3"
                      },
                      "test5": {
                        "attrOrProp": 1,
                        "digest": "Set Value (5) to Match",
                        "defaultarg": 5,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "4"
                      },
                      "test6": {
                        "attrOrProp": 1,
                        "digest": "Set Value (6) to Match",
                        "defaultarg": 6,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "5"
                      },
                      "test7": {
                        "attrOrProp": 1,
                        "digest": "Set Value (7) to Match",
                        "defaultarg": 7,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "6"
                      },
                      "test8": {
                        "attrOrProp": 1,
                        "digest": "Set Value (8) to Match",
                        "defaultarg": 8,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "7"
                      },
                      "test9": {
                        "attrOrProp": 1,
                        "digest": "Set Value (9) to Match",
                        "defaultarg": 9,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "8"
                      },
                      "test10": {
                        "attrOrProp": 1,
                        "digest": "Set Value (10) to Match",
                        "defaultarg": 10,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "9"
                      },
                      "match1": {
                        "attrOrProp": 1,
                        "digest": "Bang if input matches 0",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "match2": {
                        "attrOrProp": 1,
                        "digest": "Bang if input matches 1",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "match3": {
                        "attrOrProp": 1,
                        "digest": "Bang if input matches 2",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "match4": {
                        "attrOrProp": 1,
                        "digest": "Bang if input matches 3",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "match5": {
                        "attrOrProp": 1,
                        "digest": "Bang if input matches 4",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "match6": {
                        "attrOrProp": 1,
                        "digest": "Bang if input matches 5",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "match7": {
                        "attrOrProp": 1,
                        "digest": "Bang if input matches 6",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "match8": {
                        "attrOrProp": 1,
                        "digest": "Bang if input matches 7",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "match9": {
                        "attrOrProp": 1,
                        "digest": "Bang if input matches 8",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "match10": {
                        "attrOrProp": 1,
                        "digest": "Bang if input matches 9",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "nomatch": {
                        "attrOrProp": 1,
                        "digest": "Input if Input Doesn't Match",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "number",
                        "defaultValue": "0"
                      }
                    },
                    "inputs": [
                      {
                        "name": "input",
                        "type": [
                          "number",
                          "bang"
                        ],
                        "digest": "Number to test",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "test1",
                        "type": "number",
                        "digest": "Set Value (1) to Match",
                        "defaultarg": 1,
                        "docked": false
                      },
                      {
                        "name": "test2",
                        "type": "number",
                        "digest": "Set Value (2) to Match",
                        "defaultarg": 2,
                        "docked": false
                      },
                      {
                        "name": "test3",
                        "type": "number",
                        "digest": "Set Value (3) to Match",
                        "defaultarg": 3,
                        "docked": false
                      },
                      {
                        "name": "test4",
                        "type": "number",
                        "digest": "Set Value (4) to Match",
                        "defaultarg": 4,
                        "docked": false
                      },
                      {
                        "name": "test5",
                        "type": "number",
                        "digest": "Set Value (5) to Match",
                        "defaultarg": 5,
                        "docked": false
                      },
                      {
                        "name": "test6",
                        "type": "number",
                        "digest": "Set Value (6) to Match",
                        "defaultarg": 6,
                        "docked": false
                      },
                      {
                        "name": "test7",
                        "type": "number",
                        "digest": "Set Value (7) to Match",
                        "defaultarg": 7,
                        "docked": false
                      },
                      {
                        "name": "test8",
                        "type": "number",
                        "digest": "Set Value (8) to Match",
                        "defaultarg": 8,
                        "docked": false
                      },
                      {
                        "name": "test9",
                        "type": "number",
                        "digest": "Set Value (9) to Match",
                        "defaultarg": 9,
                        "docked": false
                      },
                      {
                        "name": "test10",
                        "type": "number",
                        "digest": "Set Value (10) to Match",
                        "defaultarg": 10,
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "match1",
                        "type": "bang",
                        "digest": "Bang if input matches 0",
                        "docked": false
                      },
                      {
                        "name": "match2",
                        "type": "bang",
                        "digest": "Bang if input matches 1",
                        "docked": false
                      },
                      {
                        "name": "match3",
                        "type": "bang",
                        "digest": "Bang if input matches 2",
                        "docked": false
                      },
                      {
                        "name": "match4",
                        "type": "bang",
                        "digest": "Bang if input matches 3",
                        "docked": false
                      },
                      {
                        "name": "match5",
                        "type": "bang",
                        "digest": "Bang if input matches 4",
                        "docked": false
                      },
                      {
                        "name": "match6",
                        "type": "bang",
                        "digest": "Bang if input matches 5",
                        "docked": false
                      },
                      {
                        "name": "match7",
                        "type": "bang",
                        "digest": "Bang if input matches 6",
                        "docked": false
                      },
                      {
                        "name": "match8",
                        "type": "bang",
                        "digest": "Bang if input matches 7",
                        "docked": false
                      },
                      {
                        "name": "match9",
                        "type": "bang",
                        "digest": "Bang if input matches 8",
                        "docked": false
                      },
                      {
                        "name": "match10",
                        "type": "bang",
                        "digest": "Bang if input matches 9",
                        "docked": false
                      },
                      {
                        "name": "nomatch",
                        "type": [
                          "number",
                          "bang"
                        ],
                        "digest": "Input if Input Doesn't Match",
                        "docked": false
                      }
                    ],
                    "helpname": "select",
                    "aliasOf": "select",
                    "classname": "sel",
                    "operator": false,
                    "versionId": 902197102,
                    "changesPatcherIO": false
                  },
                  "numinlets": 11,
                  "numoutlets": 11,
                  "outlettype": [
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-3",
                  "maxclass": "newobj",
                  "text": "loadbang",
                  "patching_rect": [
                    620,
                    30,
                    480,
                    22
                  ],
                  "rnbo_classname": "loadbang",
                  "rnbo_uniqueid": "loadbang_obj-3",
                  "rnbo_serial": 2,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "input": {
                        "attrOrProp": 1,
                        "digest": "Bang to trigger bang.",
                        "isalias": false,
                        "aliases": [],
                        "settable": false,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "output": {
                        "attrOrProp": 1,
                        "digest": "Output bang when patcher is loaded.",
                        "isalias": false,
                        "aliases": [],
                        "settable": false,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "bang"
                      },
                      "startupbang": {
                        "attrOrProp": 1,
                        "digest": "startupbang",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bang"
                      }
                    },
                    "inputs": [
                      {
                        "name": "input",
                        "type": "bang",
                        "digest": "Bang to trigger bang.",
                        "hot": true,
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "output",
                        "type": "bang",
                        "digest": "Output bang when patcher is loaded.",
                        "docked": false
                      }
                    ],
                    "helpname": "loadbang",
                    "aliasOf": "loadbang",
                    "classname": "loadbang",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 1,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-4",
                  "maxclass": "newobj",
                  "text": "outport led_rgb",
                  "patching_rect": [
                    30,
                    430,
                    480,
                    22
                  ],
                  "rnbo_classname": "outport",
                  "rnbo_uniqueid": "outport_obj-4",
                  "rnbo_serial": 3,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "tag": {
                        "attrOrProp": 2,
                        "digest": "tag to send messages to",
                        "defaultarg": 1,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "mandatory": true
                      },
                      "meta": {
                        "attrOrProp": 2,
                        "digest": "A JSON formatted string containing metadata for use by the exported code",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "defaultValue": "",
                        "label": "Metadata",
                        "displayorder": 3
                      }
                    },
                    "inputs": [
                      {
                        "name": "input",
                        "type": [
                          "bang",
                          "number",
                          "list"
                        ],
                        "digest": "number or list to send out.",
                        "hot": true,
                        "docked": false
                      }
                    ],
                    "outputs": [],
                    "helpname": "outport",
                    "aliasOf": "outport",
                    "classname": "outport",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 1,
                  "numoutlets": 0,
                  "outlettype": []
                }
              },
              {
                "box": {
                  "id": "obj-5",
                  "maxclass": "newobj",
                  "text": "sig~ 0",
                  "patching_rect": [
                    620,
                    430,
                    480,
                    22
                  ],
                  "rnbo_classname": "sig~",
                  "rnbo_uniqueid": "sig~_obj-5",
                  "rnbo_serial": 4,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "value": {
                        "attrOrProp": 1,
                        "digest": "Incoming numbers to convert",
                        "defaultarg": 1,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "0"
                      },
                      "impulse": {
                        "attrOrProp": 1,
                        "digest": "Generate a signal of 1 for specified time (ms or samples)",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "number",
                        "defaultValue": "0"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Signal output",
                        "isalias": false,
                        "aliases": [],
                        "settable": false,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "signal"
                      },
                      "unit": {
                        "attrOrProp": 2,
                        "digest": "Unit for impulse length.",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "enum": [
                          "ms",
                          "samples"
                        ],
                        "type": "enum",
                        "defaultValue": "ms"
                      }
                    },
                    "inputs": [
                      {
                        "name": "value",
                        "type": "number",
                        "digest": "Incoming numbers to convert",
                        "defaultarg": 1,
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "impulse",
                        "type": "number",
                        "digest": "Generate a signal of 1 for specified time (ms or samples)",
                        "hot": true,
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "signal",
                        "digest": "Signal output",
                        "docked": false
                      }
                    ],
                    "helpname": "sig~",
                    "aliasOf": "sig~",
                    "classname": "sig~",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    "signal"
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-6",
                  "maxclass": "newobj",
                  "text": "out~ 1",
                  "patching_rect": [
                    620,
                    480,
                    480,
                    22
                  ],
                  "rnbo_classname": "out~",
                  "rnbo_uniqueid": "out~_obj-6",
                  "rnbo_serial": 5,
                  "rnboinfo": {
                    "needsInstanceInfo": true,
                    "argnames": {
                      "in1": {
                        "attrOrProp": 1,
                        "digest": "signal sent to outlet with index 1",
                        "isalias": false,
                        "aliases": [],
                        "settable": false,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "signal"
                      },
                      "index": {
                        "attrOrProp": 2,
                        "digest": "outlet number",
                        "defaultarg": 1,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "number",
                        "mandatory": true
                      },
                      "comment": {
                        "attrOrProp": 2,
                        "digest": "mouse over comment",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol"
                      },
                      "meta": {
                        "attrOrProp": 2,
                        "digest": "A JSON formatted string containing metadata for use by the exported code",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "defaultValue": "",
                        "label": "Metadata",
                        "displayorder": 3
                      }
                    },
                    "inputs": [
                      {
                        "name": "in1",
                        "type": "signal",
                        "digest": "signal sent to outlet with index 1",
                        "displayName": "",
                        "hot": true,
                        "docked": false
                      }
                    ],
                    "outputs": [],
                    "helpname": "out~",
                    "aliasOf": "out~",
                    "classname": "out~",
                    "operator": false,
                    "versionId": 1989326771,
                    "changesPatcherIO": true
                  },
                  "numinlets": 1,
                  "numoutlets": 0,
                  "outlettype": []
                }
              },
              {
                "box": {
                  "id": "obj-7",
                  "maxclass": "newobj",
                  "text": "out~ 2",
                  "patching_rect": [
                    740,
                    480,
                    480,
                    22
                  ],
                  "rnbo_classname": "out~",
                  "rnbo_uniqueid": "out~_obj-7",
                  "rnbo_serial": 6,
                  "rnboinfo": {
                    "needsInstanceInfo": true,
                    "argnames": {
                      "in1": {
                        "attrOrProp": 1,
                        "digest": "signal sent to outlet with index 2",
                        "isalias": false,
                        "aliases": [],
                        "settable": false,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "signal"
                      },
                      "index": {
                        "attrOrProp": 2,
                        "digest": "outlet number",
                        "defaultarg": 1,
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "number",
                        "mandatory": true
                      },
                      "comment": {
                        "attrOrProp": 2,
                        "digest": "mouse over comment",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol"
                      },
                      "meta": {
                        "attrOrProp": 2,
                        "digest": "A JSON formatted string containing metadata for use by the exported code",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "symbol",
                        "defaultValue": "",
                        "label": "Metadata",
                        "displayorder": 3
                      }
                    },
                    "inputs": [
                      {
                        "name": "in1",
                        "type": "signal",
                        "digest": "signal sent to outlet with index 2",
                        "displayName": "",
                        "hot": true,
                        "docked": false
                      }
                    ],
                    "outputs": [],
                    "helpname": "out~",
                    "aliasOf": "out~",
                    "classname": "out~",
                    "operator": false,
                    "versionId": 1989326771,
                    "changesPatcherIO": true
                  },
                  "numinlets": 1,
                  "numoutlets": 0,
                  "outlettype": []
                }
              },
              {
                "box": {
                  "id": "obj-8",
                  "maxclass": "message",
                  "text": "1 0 0",
                  "patching_rect": [
                    30,
                    130,
                    460,
                    22
                  ],
                  "rnbo_classname": "message",
                  "rnbo_uniqueid": "message_obj-8",
                  "rnbo_serial": 7,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "trigger": {
                        "attrOrProp": 1,
                        "digest": "trigger the message",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "set": {
                        "attrOrProp": 1,
                        "digest": "set the message",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "list"
                      },
                      "listout": {
                        "attrOrProp": 1,
                        "digest": "listout",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Message out.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "list"
                      },
                      "storeempty": {
                        "attrOrProp": 2,
                        "digest": "Store empty lists",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false",
                        "label": "Store Empty Lists"
                      },
                      "text": {
                        "attrOrProp": 2,
                        "digest": "text",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "defaultValue": ""
                      }
                    },
                    "inputs": [
                      {
                        "name": "trigger",
                        "type": "bang",
                        "digest": "trigger the message",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "set",
                        "type": "list",
                        "digest": "set the message",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "list",
                        "digest": "Message out.",
                        "docked": false
                      }
                    ],
                    "helpname": "message",
                    "aliasOf": "message",
                    "classname": "message",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-9",
                  "maxclass": "message",
                  "text": "3 0 1 0",
                  "patching_rect": [
                    530,
                    130,
                    460,
                    22
                  ],
                  "rnbo_classname": "message",
                  "rnbo_uniqueid": "message_obj-9",
                  "rnbo_serial": 8,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "trigger": {
                        "attrOrProp": 1,
                        "digest": "trigger the message",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "set": {
                        "attrOrProp": 1,
                        "digest": "set the message",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "list"
                      },
                      "listout": {
                        "attrOrProp": 1,
                        "digest": "listout",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Message out.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "list"
                      },
                      "storeempty": {
                        "attrOrProp": 2,
                        "digest": "Store empty lists",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false",
                        "label": "Store Empty Lists"
                      },
                      "text": {
                        "attrOrProp": 2,
                        "digest": "text",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "defaultValue": ""
                      }
                    },
                    "inputs": [
                      {
                        "name": "trigger",
                        "type": "bang",
                        "digest": "trigger the message",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "set",
                        "type": "list",
                        "digest": "set the message",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "list",
                        "digest": "Message out.",
                        "docked": false
                      }
                    ],
                    "helpname": "message",
                    "aliasOf": "message",
                    "classname": "message",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-10",
                  "maxclass": "message",
                  "text": "11 0 0 1",
                  "patching_rect": [
                    30,
                    185,
                    460,
                    22
                  ],
                  "rnbo_classname": "message",
                  "rnbo_uniqueid": "message_obj-10",
                  "rnbo_serial": 9,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "trigger": {
                        "attrOrProp": 1,
                        "digest": "trigger the message",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "set": {
                        "attrOrProp": 1,
                        "digest": "set the message",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "list"
                      },
                      "listout": {
                        "attrOrProp": 1,
                        "digest": "listout",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Message out.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "list"
                      },
                      "storeempty": {
                        "attrOrProp": 2,
                        "digest": "Store empty lists",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false",
                        "label": "Store Empty Lists"
                      },
                      "text": {
                        "attrOrProp": 2,
                        "digest": "text",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "defaultValue": ""
                      }
                    },
                    "inputs": [
                      {
                        "name": "trigger",
                        "type": "bang",
                        "digest": "trigger the message",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "set",
                        "type": "list",
                        "digest": "set the message",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "list",
                        "digest": "Message out.",
                        "docked": false
                      }
                    ],
                    "helpname": "message",
                    "aliasOf": "message",
                    "classname": "message",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-11",
                  "maxclass": "message",
                  "text": "0 0 0.5 0 0 0.5 0 0 0.5 0 0 0.5 0 0 0.5 0 0 0.5 0 0 0.5 0 0 0.5 0 0 0.5 0 0 0.5 0 0 0.5 0 0 0.5",
                  "patching_rect": [
                    530,
                    185,
                    460,
                    22
                  ],
                  "rnbo_classname": "message",
                  "rnbo_uniqueid": "message_obj-11",
                  "rnbo_serial": 10,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "trigger": {
                        "attrOrProp": 1,
                        "digest": "trigger the message",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "set": {
                        "attrOrProp": 1,
                        "digest": "set the message",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "list"
                      },
                      "listout": {
                        "attrOrProp": 1,
                        "digest": "listout",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Message out.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "list"
                      },
                      "storeempty": {
                        "attrOrProp": 2,
                        "digest": "Store empty lists",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false",
                        "label": "Store Empty Lists"
                      },
                      "text": {
                        "attrOrProp": 2,
                        "digest": "text",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "defaultValue": ""
                      }
                    },
                    "inputs": [
                      {
                        "name": "trigger",
                        "type": "bang",
                        "digest": "trigger the message",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "set",
                        "type": "list",
                        "digest": "set the message",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "list",
                        "digest": "Message out.",
                        "docked": false
                      }
                    ],
                    "helpname": "message",
                    "aliasOf": "message",
                    "classname": "message",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-12",
                  "maxclass": "message",
                  "text": "12 1 1 1",
                  "patching_rect": [
                    30,
                    240,
                    460,
                    22
                  ],
                  "rnbo_classname": "message",
                  "rnbo_uniqueid": "message_obj-12",
                  "rnbo_serial": 11,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "trigger": {
                        "attrOrProp": 1,
                        "digest": "trigger the message",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "set": {
                        "attrOrProp": 1,
                        "digest": "set the message",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "list"
                      },
                      "listout": {
                        "attrOrProp": 1,
                        "digest": "listout",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Message out.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "list"
                      },
                      "storeempty": {
                        "attrOrProp": 2,
                        "digest": "Store empty lists",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false",
                        "label": "Store Empty Lists"
                      },
                      "text": {
                        "attrOrProp": 2,
                        "digest": "text",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "defaultValue": ""
                      }
                    },
                    "inputs": [
                      {
                        "name": "trigger",
                        "type": "bang",
                        "digest": "trigger the message",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "set",
                        "type": "list",
                        "digest": "set the message",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "list",
                        "digest": "Message out.",
                        "docked": false
                      }
                    ],
                    "helpname": "message",
                    "aliasOf": "message",
                    "classname": "message",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-13",
                  "maxclass": "message",
                  "text": "3.5 1 1 1",
                  "patching_rect": [
                    530,
                    240,
                    460,
                    22
                  ],
                  "rnbo_classname": "message",
                  "rnbo_uniqueid": "message_obj-13",
                  "rnbo_serial": 12,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "trigger": {
                        "attrOrProp": 1,
                        "digest": "trigger the message",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "set": {
                        "attrOrProp": 1,
                        "digest": "set the message",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "list"
                      },
                      "listout": {
                        "attrOrProp": 1,
                        "digest": "listout",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Message out.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "list"
                      },
                      "storeempty": {
                        "attrOrProp": 2,
                        "digest": "Store empty lists",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false",
                        "label": "Store Empty Lists"
                      },
                      "text": {
                        "attrOrProp": 2,
                        "digest": "text",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "defaultValue": ""
                      }
                    },
                    "inputs": [
                      {
                        "name": "trigger",
                        "type": "bang",
                        "digest": "trigger the message",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "set",
                        "type": "list",
                        "digest": "set the message",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "list",
                        "digest": "Message out.",
                        "docked": false
                      }
                    ],
                    "helpname": "message",
                    "aliasOf": "message",
                    "classname": "message",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-14",
                  "maxclass": "message",
                  "text": "1 0",
                  "patching_rect": [
                    30,
                    295,
                    460,
                    22
                  ],
                  "rnbo_classname": "message",
                  "rnbo_uniqueid": "message_obj-14",
                  "rnbo_serial": 13,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "trigger": {
                        "attrOrProp": 1,
                        "digest": "trigger the message",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "set": {
                        "attrOrProp": 1,
                        "digest": "set the message",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "list"
                      },
                      "listout": {
                        "attrOrProp": 1,
                        "digest": "listout",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Message out.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "list"
                      },
                      "storeempty": {
                        "attrOrProp": 2,
                        "digest": "Store empty lists",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false",
                        "label": "Store Empty Lists"
                      },
                      "text": {
                        "attrOrProp": 2,
                        "digest": "text",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "defaultValue": ""
                      }
                    },
                    "inputs": [
                      {
                        "name": "trigger",
                        "type": "bang",
                        "digest": "trigger the message",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "set",
                        "type": "list",
                        "digest": "set the message",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "list",
                        "digest": "Message out.",
                        "docked": false
                      }
                    ],
                    "helpname": "message",
                    "aliasOf": "message",
                    "classname": "message",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-15",
                  "maxclass": "message",
                  "text": "-1 0.5 2",
                  "patching_rect": [
                    530,
                    295,
                    460,
                    22
                  ],
                  "rnbo_classname": "message",
                  "rnbo_uniqueid": "message_obj-15",
                  "rnbo_serial": 14,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "trigger": {
                        "attrOrProp": 1,
                        "digest": "trigger the message",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "set": {
                        "attrOrProp": 1,
                        "digest": "set the message",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "list"
                      },
                      "listout": {
                        "attrOrProp": 1,
                        "digest": "listout",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Message out.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "list"
                      },
                      "storeempty": {
                        "attrOrProp": 2,
                        "digest": "Store empty lists",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false",
                        "label": "Store Empty Lists"
                      },
                      "text": {
                        "attrOrProp": 2,
                        "digest": "text",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "defaultValue": ""
                      }
                    },
                    "inputs": [
                      {
                        "name": "trigger",
                        "type": "bang",
                        "digest": "trigger the message",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "set",
                        "type": "list",
                        "digest": "set the message",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "list",
                        "digest": "Message out.",
                        "docked": false
                      }
                    ],
                    "helpname": "message",
                    "aliasOf": "message",
                    "classname": "message",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-16",
                  "maxclass": "message",
                  "text": "0 0 0",
                  "patching_rect": [
                    30,
                    350,
                    460,
                    22
                  ],
                  "rnbo_classname": "message",
                  "rnbo_uniqueid": "message_obj-16",
                  "rnbo_serial": 15,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "trigger": {
                        "attrOrProp": 1,
                        "digest": "trigger the message",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "set": {
                        "attrOrProp": 1,
                        "digest": "set the message",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "list"
                      },
                      "listout": {
                        "attrOrProp": 1,
                        "digest": "listout",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Message out.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "list"
                      },
                      "storeempty": {
                        "attrOrProp": 2,
                        "digest": "Store empty lists",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false",
                        "label": "Store Empty Lists"
                      },
                      "text": {
                        "attrOrProp": 2,
                        "digest": "text",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "defaultValue": ""
                      }
                    },
                    "inputs": [
                      {
                        "name": "trigger",
                        "type": "bang",
                        "digest": "trigger the message",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "set",
                        "type": "list",
                        "digest": "set the message",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "list",
                        "digest": "Message out.",
                        "docked": false
                      }
                    ],
                    "helpname": "message",
                    "aliasOf": "message",
                    "classname": "message",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              },
              {
                "box": {
                  "id": "obj-17",
                  "maxclass": "message",
                  "text": "0 0 1",
                  "patching_rect": [
                    530,
                    350,
                    460,
                    22
                  ],
                  "rnbo_classname": "message",
                  "rnbo_uniqueid": "message_obj-17",
                  "rnbo_serial": 16,
                  "rnboinfo": {
                    "needsInstanceInfo": false,
                    "argnames": {
                      "trigger": {
                        "attrOrProp": 1,
                        "digest": "trigger the message",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "bang"
                      },
                      "set": {
                        "attrOrProp": 1,
                        "digest": "set the message",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "inlet": true,
                        "type": "list"
                      },
                      "listout": {
                        "attrOrProp": 1,
                        "digest": "listout",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list"
                      },
                      "out": {
                        "attrOrProp": 1,
                        "digest": "Message out.",
                        "isalias": false,
                        "aliases": [],
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "outlet": true,
                        "type": "list"
                      },
                      "storeempty": {
                        "attrOrProp": 2,
                        "digest": "Store empty lists",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "bool",
                        "defaultValue": "false",
                        "label": "Store Empty Lists"
                      },
                      "text": {
                        "attrOrProp": 2,
                        "digest": "text",
                        "isalias": false,
                        "aliases": [],
                        "settable": true,
                        "attachable": false,
                        "isparam": false,
                        "deprecated": false,
                        "touched": false,
                        "type": "list",
                        "defaultValue": ""
                      }
                    },
                    "inputs": [
                      {
                        "name": "trigger",
                        "type": "bang",
                        "digest": "trigger the message",
                        "hot": true,
                        "docked": false
                      },
                      {
                        "name": "set",
                        "type": "list",
                        "digest": "set the message",
                        "docked": false
                      }
                    ],
                    "outputs": [
                      {
                        "name": "out",
                        "type": "list",
                        "digest": "Message out.",
                        "docked": false
                      }
                    ],
                    "helpname": "message",
                    "aliasOf": "message",
                    "classname": "message",
                    "operator": false,
                    "versionId": 0,
                    "changesPatcherIO": false
                  },
                  "numinlets": 2,
                  "numoutlets": 1,
                  "outlettype": [
                    ""
                  ]
                }
              }
            ],
            "lines": [
              {
                "patchline": {
                  "source": [
                    "obj-1",
                    0
                  ],
                  "destination": [
                    "obj-2",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-3",
                    0
                  ],
                  "destination": [
                    "obj-8",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-5",
                    0
                  ],
                  "destination": [
                    "obj-6",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-5",
                    0
                  ],
                  "destination": [
                    "obj-7",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-2",
                    0
                  ],
                  "destination": [
                    "obj-8",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-8",
                    0
                  ],
                  "destination": [
                    "obj-4",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-2",
                    1
                  ],
                  "destination": [
                    "obj-9",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-9",
                    0
                  ],
                  "destination": [
                    "obj-4",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-2",
                    2
                  ],
                  "destination": [
                    "obj-10",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-10",
                    0
                  ],
                  "destination": [
                    "obj-4",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-2",
                    3
                  ],
                  "destination": [
                    "obj-11",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-11",
                    0
                  ],
                  "destination": [
                    "obj-4",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-2",
                    4
                  ],
                  "destination": [
                    "obj-12",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-12",
                    0
                  ],
                  "destination": [
                    "obj-4",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-2",
                    5
                  ],
                  "destination": [
                    "obj-13",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-13",
                    0
                  ],
                  "destination": [
                    "obj-4",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-2",
                    6
                  ],
                  "destination": [
                    "obj-14",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-14",
                    0
                  ],
                  "destination": [
                    "obj-4",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-2",
                    7
                  ],
                  "destination": [
                    "obj-15",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-15",
                    0
                  ],
                  "destination": [
                    "obj-4",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-2",
                    8
                  ],
                  "destination": [
                    "obj-16",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-16",
                    0
                  ],
                  "destination": [
                    "obj-4",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-2",
                    9
                  ],
                  "destination": [
                    "obj-17",
                    0
                  ]
                }
              },
              {
                "patchline": {
                  "source": [
                    "obj-17",
                    0
                  ],
                  "destination": [
                    "obj-4",
                    0
                  ]
                }
              }
            ],
            "appversion": {
              "major": 9,
              "minor": 1,
              "revision": 4,
              "architecture": "arm64",
              "modernui": 1
            }
          },
          "varname": "instrument"
        }
      },
      {
        "box": {
          "id": "print",
          "maxclass": "newobj",
          "text": "print VOICE_PE_STUDIO",
          "patching_rect": [
            30,
            330,
            650,
            22
          ]
        }
      }
    ],
    "lines": [
      {
        "patchline": {
          "source": [
            "native16",
            0
          ],
          "destination": [
            "helper",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "native48",
            0
          ],
          "destination": [
            "helper",
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
            "helper",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "upload",
            0
          ],
          "destination": [
            "helper",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "helper",
            0
          ],
          "destination": [
            "print",
            0
          ]
        }
      }
    ]
  }
}
