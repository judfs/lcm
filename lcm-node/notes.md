Have node installed. I recommend using `nvm` for this. https://github.com/nvm-sh/nvm

https://github.com/nodejs/node-addon-api/blob/main/doc/setup.md

https://github.com/nodejs/node-addon-examples

```
npm install -g node-gyp
```

`npx node-gyp` does not work for some reason. Must use a global install unless the path errors can be resolved.

```
node-gyp configure
node-gyp build
node hello.js 
```