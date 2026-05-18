import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  standalone: true,
  imports: [RouterOutlet],
  template: `<div class="config-content"><router-outlet></router-outlet></div>`,
  styles: [`:host { display: block; height: 100%; } .config-content { height: 100%; overflow-y: auto; }`],
})
export class ConfigurationShellComponent {}
