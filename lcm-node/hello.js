import bindings from "bindings";
const addon = bindings("lcm_node");

const obj = new addon.MyObject(10);
console.log(obj.plusOne()); // 11
console.log(obj.plusOne()); // 12
console.log(obj.plusOne()); // 13

const N = 5;
let i = 0;
while (i < N) {
  i++;
  await obj.handle(); // Will print the channel names for now
}
