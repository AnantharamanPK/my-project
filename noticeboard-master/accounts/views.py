from django.contrib.auth import login
from django.shortcuts import render, redirect
from .forms import SignUpForm

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import UpdateView


def signup(request):
    if request.user.is_authenticated:
        return redirect('notices:home')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('notices:home')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})



@method_decorator(login_required, name='dispatch')
class UserUpdateView(UpdateView):
    model = User
    fields = ('first_name', 'last_name', 'email', )
    template_name = 'accounts/my_account.html'
    success_url = reverse_lazy('accounts:my_account')

    def get_object(self):
        return self.request.user
    
def live_search(request):
    query = request.GET.get('q', '')
    if len(query) > 0:
        # Filter notices by title
        results = Notice.objects.filter(title__icontains=query)[:5] # Limit to 5 results
        data = [{'id': n.id, 'title': n.title} for n in results]
    else:
        data = []
    return JsonResponse({'results': data})