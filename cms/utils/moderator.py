from django.core.exceptions import ObjectDoesNotExist
import datetime
from django.utils.translation import ugettext as _
from cms import settings as cms_settings
from cms.models import Page, GlobalPagePermission, PagePermission, MASK_PAGE,\
    PageModeratorState
from cms.utils.permissions import get_current_user

def page_changed(page, old_page=None):
    """Called from page post save signal. If page already had pk, old version
    of page is provided in old_page argument.
    """
    # get user from thread locals
    user = get_current_user()
    
    if not old_page:
        # just newly created page
        PageModeratorState(user=user, page=page, action=PageModeratorState.ACTION_ADD).save()
    
    if (old_page is None and page.published) or \
        (old_page and not old_page.published == page.published):
        action = page.published and PageModeratorState.ACTION_PUBLISH or PageModeratorState.ACTION_UNPUBLISH
        PageModeratorState(user=user, page=page, action=action).save()
        

def update_moderation_message(page, message):
    """This is bit special.. It updates last page state made from current user
    for given page. Its called after page is saved - page state is created when
    page gets saved (in signal), so this might have a concurrency issue, but 
    probably will work in 99,999%.
    
    If any page state is'nt found in last UPDATE_TOLERANCE seconds, a new state
    will be created instead of affecting old message.    
    """
    print ">>> update message:", message
    
    UPDATE_TOLERANCE = 30 # max in last 30 seconds
    
    user = get_current_user()
    created = datetime.datetime.now() - datetime.timedelta(seconds=UPDATE_TOLERANCE)
    print "> created:", created
    try:
        state = page.pagemoderatorstate_set.filter(user=user, created__gt=created).order_by('-created')[0]
        # just state without message!!
        assert not state.message  
    except (IndexError, AssertionError):
        state = PageModeratorState(user=user, page=page, action=PageModeratorState.ACTION_CHANGED)
    
    
    
    state.message = message
    state.save()
    
def page_moderator_state(request, page):
    """Return moderator page state from page.moderator_state, but also takes 
    look if current user is in the approvement path, and should approve the this 
    page. In this case return 100 as an state value. 
    """
    I_APPROVE = 100
    
    state, label = page.moderator_state, None
    
    if cms_settings.CMS_MODERATOR:
        if state == Page.MODERATOR_NEED_APPROVEMENT and page.has_moderate_permission(request):
            try:
                page.pagemoderator_set.get(user=request.user)
                state = I_APPROVE
                label = _('approve')
            except ObjectDoesNotExist:
                pass
    elif not state is Page.MODERATOR_APPROVED:
        # if no moderator, we have just 2 states => changed / unchanged
        state = Page.MODERATOR_CHANGED
    
    if not label:
        label = dict(page.moderator_state_choices)[state]
    return dict(state=state, label=label)
    