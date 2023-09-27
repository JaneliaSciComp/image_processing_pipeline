var plan = require('flightplan');

var config = {
  srcDir: '/opt/dev/lightsheetInterfaceDraft/lightsheetInterface',  // location on the remote server
  projectDir: '/opt/projects/lightsheet',  // location on the remote server
  pythonPath: '/usr/bin/python3',
  keepReleases: 3,
  username: 'flask',
};

plan.target('local', {
  host: 'localhost',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: true
});

plan.target('staging', {
  host: 'lightsheet',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: true
});

plan.target('test', {
  host: 'pipeline-test',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: true
});

plan.target('production', {
  host: 'pipeline',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: true
});

plan.target('test-new', {
  host: 'pipeline-test-new',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: true
});

plan.target('production-new', {
  host: 'pipeline-new',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: false
});

plan.local('version', function(local) {
  local.log('create new version number and add as a git commit')
  var versionType = plan.runtime.options.argv.remain[1];
  var command = local.exec('npm version ' + versionType);
  var command = local.exec('cat package.json | grep version');
  var myVersion =  "v" + (JSON.stringify(command).split(':')[3]).split('"')[1].replace('\\','');
  var command = local.exec('git add package.json; git commit -m' + '"' + myVersion + '"');
});

// Check if there are files that have not been committed to git. This stops
// us from deploying code in an inconsistent state. It also prevents slapdash
// changes from being deployed without a log of who added them in github. Not
// fool proof, but better than nothing.
plan.local('deploy', function(local) {
  if (plan.runtime.target === 'production' || plan.runtime.options.gitCheck) {
    local.log('checking git status...');
    var result = local.exec('git status --porcelain', {silent: true});

    if (result.stdout) {
      local.log(result.stdout);
      plan.abort('Uncommited files found, see list above');
    }
  } else {
    local.log('skipping git check!!!');
  }
});


plan.remote('deploy', function(remote) {
  config.deployTo = config.projectDir + '/releases/' + (new Date().getTime());
  remote.log('Creating webroot');
  remote.exec('mkdir -p ' + config.deployTo);
});

// Gets a list of files that git knows about and sends them to the
// target.
plan.local('deploy', function (local) {
  local.log('Transferring website files');
  var files = local.git('ls-files', {silent: true});
  local.transfer(files, config.deployTo + '/');
});

plan.remote('deploy',function (remote) {
  remote.log('Linking to new release');
  remote.exec('ln -nfs ' + config.deployTo + ' ' +
    config.projectDir + '/current');

  remote.log('Checking for stale releases');
  var releases = getReleases(remote);

  if (releases.length > config.keepReleases) {
    var removeCount = releases.length - config.keepReleases;
    remote.log('Removing ' + removeCount + ' stale release(s)');

    releases = releases.slice(0, removeCount);
    releases = releases.map(function (item) {
      return config.projectDir + '/releases/' + item;
      });

    remote.exec('rm -rf ' + releases.join(' '));
  }
});

plan.remote('deploy', function(remote) {
  remote.log('Create virtualenv');
  remote.exec('cd ' + config.projectDir + '/current' + '; virtualenv env --no-site-packages -p ' + config.pythonPath);
});

plan.remote('deploy', function(remote) {
  remote.log('Install the requirements');
  // use pip9 due to bug reported here: https://stackoverflow.com/questions/49854465/pythonpip-install-bson-error
  remote.exec('cd ' + config.projectDir + '/current' + '; source env/bin/activate; pip install -U pip; pip install -r requirements.txt --no-cache-dir');
});

plan.remote('deploy', function(remote) {
  remote.log('Copy over lightsheet-config.cfg');
  remote.exec('cp ' + config.projectDir + '/lightsheet-config.cfg ' + config.projectDir + '/current/app/');
});

plan.remote('deploy', function(remote) {
  remote.log('Copy over env_config.py');
  remote.exec('cp ' + config.projectDir + '/env_config.py ' + config.projectDir + '/current/');
});

// plan.remote('deploy', function(remote) {
//   remote.log('Create upload folder');
//   remote.exec('cd ' + config.projectDir + '/current' + '; mkdir upload');
// });

plan.remote('deploy', function(remote) {
  remote.log('Restart application');
  remote.exec('sudo /usr/local/bin/flask_restart.sh');
});

plan.remote('rollback', function(remote) {
  remote.log('Rolling back release');
  var releases = getReleases(remote);
  if (releases.length > 1) {
    var oldCurrent = releases.pop();
    var newCurrent = releases.pop();
    remote.log('Linking current to ' + newCurrent);
    remote.exec('ln -nfs ' + config.projectDir + '/releases/' + newCurrent + ' '
      + config.projectDir + '/current');

    remote.log('Removing ' + oldCurrent);
    remote.sudo('rm -rf ' + config.projectDir + '/releases/' + oldCurrent, {user: config.root});
  }

});

plan.remote(['default','uptime'], function(remote) {
  remote.exec('uptime');
  remote.exec('whoami');
});

function getReleases(remote) {
  var releases = remote.exec('ls ' + config.projectDir +
    '/releases', {silent: true});

  if (releases.code === 0) {
    releases = releases.stdout.trim().split('\n');
    return releases;
  }

  return [];
}
