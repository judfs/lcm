{
  "targets": [ 
    { 
      "target_name": "lcm_node", 
      "sources": [ "src/binding.cc" ],
      "include_dirs": [
        "<!@(node -p \"require('node-addon-api').include\")"
      ], 
      'defines': [ 'NAPI_DISABLE_CPP_EXCEPTIONS' ],
      "conditions": [
        ['OS=="win"', {
          'libraries': [
            # TODO
          ],
        }, { # OS!="win"

          'libraries': [
            "-llcm",
          ],

        }],
      ]
    } 
  ],
}