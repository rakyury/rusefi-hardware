// Render actual KiCad-exported SVGs. Run with Node and sharp on NODE_PATH.
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
async function main() {
  const folder = path.join(__dirname, 'reports', 'svg');
  for (const file of fs.readdirSync(folder)) {
    let name;
    const channel = file.match(/-Ignition ([1-8])/);
    if (channel) name = `ignition_${channel[1]}.svg`;
    else if (file.includes('-Ignition permission')) name = 'ignition_common.svg';
    else name = file;
    if (name !== file) fs.renameSync(path.join(folder, file), path.join(folder, name));
    const exported = path.join(folder, name);
    fs.writeFileSync(exported, fs.readFileSync(exported, 'utf8').replace(/[\t ]+$/gm, ''));
  }
  for (const name of ['ignition_1','ignition_common','ignition_validation']) {
    await sharp(path.join(folder, `${name}.svg`), { density: 140 })
      .resize({width:2400}).png().toFile(path.join(__dirname,'reports',`${name}.png`));
  }
}
main().catch(error => { console.error(error); process.exit(1); });
