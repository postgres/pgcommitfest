{%load commitfest%}
<tr>
<th>CFBot Status</th>
 <td>
  {%if not cfbot_branch %}
   <span class="label label-default">Not processed</span></a>
  {%elif cfbot_branch.needs_rebase_since %}
   <a href="{{cfbot_branch.apply_url}}">
    <span class="label label-warning" title="View git apply logs">Needs rebase!</span></a>
   Needs rebase {% cfsince cfbot_branch.needs_rebase_since %}. {%if cfbot_branch.failing_since and cfbot_branch.failing_since != cfbot_branch.needs_rebase_since %}Failing {% cfsince cfbot_branch.failing_since %}. {%endif%}<br>Additional links previous successfully applied patch (outdated):<br>
   <a href="https://github.com/postgresql-cfbot/postgresql/compare/cf/{{patch.id}}~1...cf/{{patch.id}}" title="View previous successfully applied patch set on GitHub"><img class="github-logo" src="/media/commitfest/github-mark.svg"/></a>
   <a href="https://cirrus-ci.com/github/postgresql-cfbot/postgresql/cf%2F{{patch.id}}">
    <span class="label label-default">Summary</span></a>
  {%else%}
   <a href="https://github.com/postgresql-cfbot/postgresql/compare/cf/{{patch.id}}~1...cf/{{patch.id}}" title="View last patch set on GitHub"><img class="github-logo" src="/media/commitfest/github-mark.svg"/></a>
   <a href="https://cirrus-ci.com/github/postgresql-cfbot/postgresql/cf%2F{{patch.id}}">
    <span class="label label-default">Summary</span></a>
   {%for c in cfbot_tasks %}
    {%if c.status == 'COMPLETED'%}
     <a href="https://cirrus-ci.com/task/{{c.task_id}}" title="{{c.task_name}}: {{c.status}}"><img src="/media/commitfest/new_success.svg"/></a>
    {%elif c.status == 'CREATED' or c.status == 'SCHEDULED' %}
     <a href="https://cirrus-ci.com/task/{{c.task_id}}" title="{{c.task_name}}: {{c.status}}"><img src="/media/commitfest/waiting_to_start.svg"/></a>
    {%elif c.status == 'EXECUTING' %}
     <a href="https://cirrus-ci.com/task/{{c.task_id}}" title="{{c.task_name}}: {{c.status}}"><img src="/media/commitfest/running.svg"/></a>
    {%else %}
     <a href="https://cirrus-ci.com/task/{{c.task_id}}" title="{{c.task_name}}: {{c.status}}"><img src="/media/commitfest/new_failure.svg"/></a>
    {%endif%}
   {%endfor%}
  {%endif%}
  {%if cfbot_branch %}
   <button class="btn btn-default" title="This adds the following to your clipboard (needs to be run in an existing git repo):
                                          git remote add commitfest https://github.com/postgresql-cfbot/postgresql.git
                                          git fetch commitfest cf/{{patch.id}}
                                          git checkout commitfest/cf/{{patch.id}}" onclick="addGitCheckoutToClipboard({{patch.id}})">Copy git checkout commands</button>
  {%endif%}
 </a>
</td>
</tr>
<tr>
 <th>CFBot Calculations</th>
 <td>
  {%if cfbot_branch and cfbot_branch.commit_id %}
   {%if cfbot_branch.version %}
    Patch version: {{ cfbot_branch.version }},
   {%endif%}
   Patch count: {{ cfbot_branch.patch_count }},
   First patch: <span class="additions">+{{ cfbot_branch.first_additions }}</span><span class="deletions">&#8722;{{ cfbot_branch.first_deletions }}</span>,
   All patches: <span class="additions">+{{ cfbot_branch.all_additions }}</span><span class="deletions">&#8722;{{ cfbot_branch.all_deletions }}</span>
  {%else%}
   Unknown
  {%endif%}
 </td>
</tr>
