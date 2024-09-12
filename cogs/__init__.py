from pkgutil import iter_modules
EXTENSIONS = [module.name for module in iter_modules(__path__, f'{__package__}.')]
if 'cogs.ranks' in EXTENSIONS: 
    EXTENSIONS.remove('cogs.ranks')
    EXTENSIONS.append('cogs.ranks')
if 'cogs.models' in EXTENSIONS: 
    EXTENSIONS.remove('cogs.models')
    EXTENSIONS.append('cogs.models')
